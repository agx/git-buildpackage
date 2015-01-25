# vim: set fileencoding=utf-8 :

from .. import context

import os
import shutil
import subprocess
import tempfile

import gbp.log
import gbp.errors
from gbp.deb.changelog import ChangeLog

from gbplogtester import GbpLogTester
from debiangittestrepo import DebianGitTestRepo

__all__ = ['GbpLogTester, DebianGitTestRepo', 'OsReleaseFile',
           'MockedChangeLog', 'get_dch_default_urgency' ]

class OsReleaseFile(object):
    """Repesents a simple file with key-value pairs"""

    def __init__(self, filename):
        self._values = {}

        try:
            with open(filename, 'r') as filed:
                for line in filed.readlines():
                    try:
                        key, value = line.split('=', 1)
                    except ValueError:
                        pass
                    else:
                        self._values[key] = value.strip()
        except IOError as err:
            gbp.log.info('Failed to read OS release file %s: %s' %
                            (filename, err))

    def __getitem__(self, key):
        if key in self._values:
            return self._values[key]
        return None

    def __contains__(self, key):
        return key in self._values

    def __str__(self):
        return str(self._values)

    def __repr__(self):
        return repr(self._values)

class MockedChangeLog(ChangeLog):
    contents = """foo (%s) experimental; urgency=low

  %s

 -- Debian Maintainer <maint@debian.org>  Sat, 01 Jan 2012 00:00:00 +0100"""

    def __init__(self, version, changes = "a important change"):
        ChangeLog.__init__(self,
                           contents=self.contents % (version, changes))


def get_dch_default_urgency():
    """Determine the default urgency level used by dch"""
    urgency = 'medium'
    tempdir = tempfile.mkdtemp()
    tmp_dch_name = os.path.join(tempdir, 'changelog')
    try:
        dch_cmd = ['dch', '--create', '--empty', '--changelog', tmp_dch_name,
                   '--package=foo', '--newversion=1',
                   '--distribution=UNRELEASED']
        ret = subprocess.Popen(dch_cmd).wait()
    except OSError:
        pass
    else:
        if ret == 0:
            with open(tmp_dch_name) as dchfile:
                header = dchfile.readline().strip()
                urgency = header.split()[-1].replace('urgency=', '')
    finally:
        if os.path.isdir(tempdir):
            shutil.rmtree(tempdir)
    return urgency

