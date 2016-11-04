# vim: set fileencoding=utf-8 :
"""Test L{gbp.command_wrappers.Command}'s tarball unpack"""

import unittest
import mock
import functools

from gbp.command_wrappers import Command, CommandExecFailed
from . testutils import GbpLogTester


def patch_popen(stdout='', stderr='', returncode=1):
    """Decorator to easily set the return value of popen.communicate()"""
    def patch_popen_decorator(func):
        @functools.wraps(func)
        def wrap(self):
            with mock.patch('subprocess.Popen') as create_mock:
                popen_mock = mock.Mock(**{'returncode': returncode,
                                          'communicate.return_value': (stdout, stderr)})
                create_mock.return_value = popen_mock
                return func(self, create_mock)
        return wrap
    return patch_popen_decorator


class TestCommandWrapperFailures(unittest.TestCase, GbpLogTester):
    def setUp(self):
        self.false = Command('/does/not/matter')
        self.log_tester = GbpLogTester()
        self.log_tester._capture_log(True)

    def tearDown(self):
        self.log_tester._capture_log(False)

    @patch_popen(stdout='', stderr='', returncode=1)
    def test_log_default_error_msg(self, create_mock):
        with self.assertRaises(CommandExecFailed):
            self.false.__call__()
        self.log_tester._check_log(0, "gbp:error: '/does/not/matter' failed: it exited with 1")
        self.assertEqual(self.false.retcode, 1)
        self.assertEqual(self.false.stderr, '')
        self.assertEqual(self.false.stdout, '')

    @patch_popen(stdout='', stderr='we have a problem', returncode=1)
    def test_log_use_stderr_for_err_message(self, create_mock):
        self.false.capture_stderr = True
        self.false.run_error = "Erpel {stderr}"
        with self.assertRaises(CommandExecFailed):
            self.false.__call__()
        self.log_tester._check_log(0, "gbp:error: Erpel we have a problem")
        self.assertEqual(self.false.retcode, 1)
        self.assertEqual(self.false.stderr, 'we have a problem')
        self.assertEqual(self.false.stdout, '')

    @patch_popen(stdout='we have a problem', stderr='', returncode=1)
    def test_log_use_stdout_for_err_message(self, create_mock):
        self.false.capture_stdout = True
        self.false.run_error = "Erpel {stdout}"
        with self.assertRaises(CommandExecFailed):
            self.false.__call__()
        self.log_tester._check_log(0, "gbp:error: Erpel we have a problem")
        self.assertEqual(self.false.retcode, 1)
        self.assertEqual(self.false.stderr, '')
        self.assertEqual(self.false.stdout, 'we have a problem')

    def test_log_use_err_or_reason_for_error_messge_reason(self):
        self.false.run_error = "AFAIK {stderr_or_reason}"
        with self.assertRaises(CommandExecFailed):
            self.false.__call__()
        self.log_tester._check_log(0, "gbp:error: AFAIK execution failed: .Errno 2. No such file or directory")
        self.assertEqual(self.false.retcode, 1)

    @patch_popen(stderr='we have a problem', returncode=1)
    def test_log_use_err_or_reason_for_error_messge_error(self, create_mock):
        self.false.run_error = "Erpel {stderr_or_reason}"
        with self.assertRaises(CommandExecFailed):
            self.false.__call__()
        self.log_tester._check_log(0, "gbp:error: Erpel we have a problem")
        self.assertEqual(self.false.retcode, 1)

    @patch_popen(returncode=0)
    def test_no_log_on_success(self, create_mock):
        self.false.__call__()
        self.log_tester._check_log_empty()
        self.assertEqual(self.false.retcode, 0)
