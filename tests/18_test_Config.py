# vim: set fileencoding=utf-8 :

import os
import unittest
from gbp.config import GbpConfig, GbpConfArgParser
from .testutils import GbpLogTester


class TestConfigParser(unittest.TestCase, GbpLogTester):
    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        GbpLogTester.__init__(self)

    def setUp(self):
        self.conffiles_save = os.environ.get('GBP_CONF_FILES')
        self.confname = 'tests/data/test1.conf'
        self.assertTrue(os.stat(self.confname))
        os.environ['GBP_CONF_FILES'] = self.confname
        self._capture_log(True)

    def tearDown(self):
        if self.conffiles_save:
            os.environ['GBP_CONF_FILES'] = self.conffiles_save
        self._capture_log(False)

    def test_default(self):
        """
        A value only in the default section should be available in all commands
        """
        for n in range(1, 5):
            for prefix in ['', 'git-', 'gbp-']:
                parser = GbpConfArgParser.create_parser(prog='%scmd%d' %
                                                        (prefix, n))
                self.assertEqual(parser.config.get_value('default_option'), 'default_default1')

    def test_single_override(self):
        """
        A value in any command section should override the default
        """
        for prefix in ['', 'git-', 'gbp-']:
            parser = GbpConfArgParser.create_parser(prog='%scmd1' % prefix)
            self.assertEqual(parser.config.get_value('single_override_option1'), 'single_override_value1')
        # No deprecation warning since the test1.conf section is [cmd1]
        self._check_log_empty()

    def test_single_git_override(self):
        """
        A value in any git-command section should override the default
        """
        for prefix in ['', 'git-']:
            parser = GbpConfArgParser.create_parser(prog='%scmd2' % prefix)
            self.assertEqual(parser.config.get_value('single_git_override_option1'), 'single_git_override_value1')
        for line in range(0, 2):
            self._check_log(line, ".*Old style config section \[git-cmd2\] found please rename to \[cmd2\]")

    def test_single_gbp_override(self):
        """
        A value in any gbp-command section should override the default
        """
        for prefix in ['', 'gbp-']:
            parser = GbpConfArgParser.create_parser(prog='%scmd3' % prefix)
            self.assertEqual(parser.config.get_value('single_gbp_override_option1'), 'single_gbp_override_value1')
        for line in range(0, 2):
            self._check_log(line, ".*Old style config section \[gbp-cmd3\] found please rename to \[cmd3\]")

    def test_single_git_override_disabled_deprecations(self):
        """
        With disabled deprecations we shouldn't see a log line
        """
        for prefix in ['', 'git-']:
            os.environ['GBP_DISABLE_SECTION_DEPRECATION'] = 'true'
            parser = GbpConfArgParser.create_parser(prog='%scmd2' % prefix)
            self.assertEqual(
                parser.config.get_value('single_git_override_option1'),
                'single_git_override_value1')
        for line in range(0, 2):
            self._check_log_empty()
        os.environ.pop('GBP_DISABLE_SECTION_DEPRECATION')

    def test_new_overrides_git(self):
        """
        A value in the cmd section should override the old git-cmd section independent from
        how we're invoked
        """
        for n in range(4, 6):
            for prefix in ['', 'git-']:
                cmd = '%scmd%d' % (prefix, n)
                parser = GbpConfArgParser.create_parser(prog=cmd)
                actual = parser.config.get_value('new_overrides_git_option1')
                expected = 'new_overrides_git_value1'
                self.assertEqual(actual, expected, "%s != %s for %s" % (actual, expected, cmd))

    def test_get_conf_file_value(self):
        """
        Read a single value from the parsed config
        """
        parser = GbpConfArgParser.create_parser(prog='cmd4')
        self.assertEqual(parser.get_conf_file_value('new_overrides_git_option1'),
                         'new_overrides_git_value1')
        self.assertEqual(parser.get_conf_file_value('doesnotexist'), None)

    def test_param_list(self):
        parser = GbpConfArgParser.create_parser(prog='cmd4')

        branch_group = parser.add_argument_group("branch options", "branch update and layout options")
        branch_group.add_conf_file_arg("--upstream-branch", dest="upstream_branch")
        branch_group.add_conf_file_arg("--debian-branch", dest="upstream_branch")
        parser.add_conf_file_arg("--color", dest="color", type='tristate')

        params = parser.conf_file_args
        self.assertTrue('upstream-branch' in params)
        self.assertTrue('debian-branch' in params)
        self.assertTrue('color' in params)

    def test_short_option_with_prefix(self):
        """Options with short options can't have a prefix"""
        class TestConfig(GbpConfig):
            list_opts = []
            defaults = {'withshort': 'foo'}

        class TestParser(GbpConfArgParser):
            short_opts = {'withshort': '-S'}

        config = TestConfig('cmd')
        parser = TestParser.create_parser(prefix='p', prog='cmd', config=config)
        with self.assertRaisesRegexp(ValueError, "Options with prefix cannot have a short option"):
            parser.add_conf_file_arg("--withshort", dest="with_short", help="foo")

    def test_short_option(self):
        class TestConfig(GbpConfig):
            list_opts = []
            defaults = {'withshort': 'foo'}

        class TestParser(GbpConfArgParser):
            short_opts = {'withshort': '-S'}

        config = TestConfig('cmd')
        parser = TestParser.create_parser(prog='cmd', config=config)
        parser.add_conf_file_arg("--withshort", dest="with_short", help="foo")
        self.assertTrue('withshort' in parser.conf_file_args)
        self.assertEquals(len(parser.conf_file_args), 1)
        args = parser.parse_args(['--withshort', 'bar'])
        self.assertEquals(getattr(args, 'with_short'), 'bar')
        args = parser.parse_args(['-S', 'baz'])
        self.assertEquals(getattr(args, 'with_short'), 'baz')
