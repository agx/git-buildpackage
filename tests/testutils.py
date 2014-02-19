# vim: set fileencoding=utf-8 :

from . import context

import os
import subprocess
import unittest

import gbp.log
import gbp.deb.git
import gbp.errors
from gbp.deb.changelog import ChangeLog

class DebianGitTestRepo(unittest.TestCase):
    """Scratch repo for a single unit test"""

    def setUp(self):
        self.tmpdir = context.new_tmpdir(__name__)

        repodir = self.tmpdir.join('test_repo')
        self.repo = gbp.deb.git.DebianGitRepository.create(repodir)

    def tearDown(self):
        context.teardown()

    def add_file(self, name, content=None, msg=None):
        """
        Add a single file with name I{name} and content I{content}. If
        I{content} is C{none} the content of the file is undefined.

        @param name: the file's path relativ to the git repo
        @type name: C{str}
        @param content: the file's content
        @type content: C{str}
        """
        path = os.path.join(self.repo.path, name)

        d = os.path.dirname(path)
        if not os.path.exists(d):
            os.makedirs(d)

        with open(path, 'w+') as f:
            content == None or f.write(content)
        self.repo.add_files(name, force=True)
        self.repo.commit_files(path, msg or "added %s" % name)

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
    try:
        popen = subprocess.Popen(['dch', '--version'], stdout=subprocess.PIPE)
        out, _err = popen.communicate()
    except OSError:
        urgency='medium'
    else:
        verstr = out.splitlines()[0].split()[-1]
        major, minor = verstr.split('.')[0:2]
        if int(major) <= 2 and int(minor) <= 12:
            urgency = 'low'
        else:
            urgency = 'medium'
    return urgency

