# vim: set fileencoding=utf-8 :

import re
from six import StringIO
from nose.tools import ok_, assert_less

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
        if capture:
            assert self._log is None, "Log capture already started"
            self._log = StringIO()
            self._loghandler = gbp.log.GbpStreamHandler(self._log, False)
            self._loghandler.addFilter(gbp.log.GbpFilter([gbp.log.WARNING,
                                                          gbp.log.ERROR]))
            handlers = list(gbp.log.LOGGER.handlers)
            for hdl in handlers:
                gbp.log.LOGGER.removeHandler(hdl)
            gbp.log.LOGGER.addHandler(self._loghandler)
        else:
            assert self._log is not None, "Log capture not started"
            gbp.log.LOGGER.removeHandler(self._loghandler)
            self._loghandler.close()
            self._loghandler = None
            self._log.close()
            self._log = None

    def _get_log(self):
        """Get the captured log output"""
        self._log.seek(0)
        return self._log.readlines()

    def _check_log_empty(self):
        """Check that nothig was logged"""
        output = self._get_log()
        ok_(output == [], "Log is not empty: %s" % output)

    def _check_log(self, linenum, regex):
        """Check that the specified line on log matches expectations"""
        if self._log is None:
            raise Exception("BUG in unittests: no log captured!")
        log = self._get_log()
        assert_less(linenum, len(log),
                    "Not enough log lines: %d" % len(log))
        output = self._get_log()[linenum].strip()
        ok_(re.match(regex, output),
            "Log entry '%s' doesn't match '%s'" % (output, regex))

    def _clear_log(self):
        """Clear the mock strerr"""
        if self._log is not None:
            self._log.seek(0)
            self._log.truncate()
