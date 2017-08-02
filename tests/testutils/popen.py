# vim: set fileencoding=utf-8 :

import functools
import mock


def patch_popen(stdout=b'', stderr=b'', returncode=1):
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
