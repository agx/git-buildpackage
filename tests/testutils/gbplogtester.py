# vim: set fileencoding=utf-8 :

import re
from six import StringIO
from nose.tools import eq_, ok_     # pylint: disable=E0611

import gbp.log

class GbpLogTester(object):
    """
    Helper class for tests that need to capture logging output
    """
    def __init__(self):
        """Object initialization"""
        self._log = None
        self._loghandler = None

    def _capture_log(self, capture=True):
        """ Capture log"""
        if capture and self._log is None:
            self._log = StringIO()
            self._loghandler = gbp.log.GbpStreamHandler(self._log, False)
            self._loghandler.addFilter(gbp.log.GbpFilter([gbp.log.WARNING,
                                                          gbp.log.ERROR]))
            for hdl in gbp.log.LOGGER.handlers:
                gbp.log.LOGGER.removeHandler(hdl)
            gbp.log.LOGGER.addHandler(self._loghandler)
        elif self._log is not None:
            gbp.log.LOGGER.removeHandler(self._loghandler)
            self._loghandler.close()
            self._loghandler = None
            self._log.close()
            self._log = None

    def _get_log(self):
        """Get the captured log output"""
        self._log.seek(0)
        return self._log.readlines()

    def _check_log(self, linenum, regex):
        """Check that the specified line on log matches expectations"""
        if self._log is None:
            raise Exception("BUG in unittests: no log captured!")
        output = self._get_log()[linenum].strip()
        ok_(re.match(regex, output),
            "Log entry '%s' doesn't match '%s'" % (output, regex))

    def _clear_log(self):
        """Clear the mock strerr"""
        if self._log is not None:
            self._log.seek(0)
            self._log.truncate()
