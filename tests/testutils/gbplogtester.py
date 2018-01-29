# vim: set fileencoding=utf-8 :

import re
from io import StringIO
from nose.tools import ok_, assert_less

import gbp.log


class GbpLogTester(object):
    """
    Helper class for tests that need to capture logging output
    """
    def __init__(self):
        """Object initialization"""
        # Warnings and Errors
        self._log = None
        self._loghandler = None
        # Info and Debug messages
        self._log_info = None
        self._loghandler_info = None

    def _capture_log(self, capture=True):
        """ Capture log"""
        if capture:
            assert self._log is None, "Log capture already started"

            handlers = list(gbp.log.LOGGER.handlers)
            for hdl in handlers:
                gbp.log.LOGGER.removeHandler(hdl)

            self._log = StringIO()
            self._loghandler = gbp.log.GbpStreamHandler(self._log, False)
            self._loghandler.addFilter(gbp.log.GbpFilter([gbp.log.WARNING,
                                                          gbp.log.ERROR]))

            self._log_info = StringIO()
            self._loghandler_info = gbp.log.GbpStreamHandler(self._log_info, False)
            self._loghandler_info.addFilter(gbp.log.GbpFilter([gbp.log.DEBUG,
                                                               gbp.log.INFO]))
            gbp.log.LOGGER.addHandler(self._loghandler)
            gbp.log.LOGGER.addHandler(self._loghandler_info)
        else:
            assert self._log is not None, "Log capture not started"
            gbp.log.LOGGER.removeHandler(self._loghandler)
            self._loghandler.close()
            self._log.close()
            self._loghandler = self._log = None

            gbp.log.LOGGER.removeHandler(self._loghandler_info)
            self._loghandler_info.close()
            self._log_info.close()
            self._loghandler_info = self._log_info = None

    def _get_log(self):
        """Get the captured log output"""
        self._log.seek(0)
        return self._log.readlines()

    def _get_log_info(self):
        self._log_info.seek(0)
        return self._log_info.readlines()

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

    def _check_in_log(self, regex):
        """Check that at least one line in log matches expectations"""
        found = False
        if self._log is None:
            raise Exception("BUG in unittests: no log captured!")
        log = self._get_log()
        for line in log:
            if re.match(regex, line):
                found = True
                break
        ok_(found, "No line of %s matched '%s'" % (log, regex))

    def _check_in_info_log(self, regex):
        """Check that at least one line in info log matches expectations"""
        found = False
        if self._log_info is None:
            raise Exception("BUG in unittests: no log captured!")
        log = self._get_log_info()
        for line in log:
            if re.match(regex, line):
                found = True
                break
        ok_(found, "No line of %s matched '%s'" % (log, regex))

    def _clear_log(self):
        """Clear the mock strerr"""
        if self._log is not None:
            self._log.seek(0)
            self._log.truncate()
