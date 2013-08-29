# vim: set fileencoding=utf-8 :
#
# (C) 2012 Intel Corporation <markus.lehtonen@linux.intel.com>
#     2013 Guido Günther <agx@sigxcpu.org>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""
Module for testing individual command line tools of the git-buildpackage suite
"""

import os
import shutil
import tempfile
from StringIO import StringIO

from nose import SkipTest

import gbp.log
from  gbp.git import GitRepository, GitRepositoryError

class ComponentTestGitRepository(GitRepository):
    """Git repository class for component tests"""
    def submodule_status(self):
        """
        Determine submodules and their status
        """
        out, err, ret = self._git_inout('submodule', ['status'],
                                        capture_stderr=True)
        if ret:
            raise GitRepositoryError("Cannot get submodule status: %s" %
                                     err.strip())
        submodules = {}
        for line in out.splitlines():
            module = line.strip()
            # Uninitialized
            status = module[0]
            if status == '-':
                sha1, path = module[1:].rsplit(' ', 1)
            else:
                commitpath = module[1:].rsplit(' ', 1)[0]
                sha1, path = commitpath.split(' ', 1)
            submodules[path] = (status, sha1)
        return submodules

    @classmethod
    def check_testdata(cls, data):
        """Check whether the testdata is current"""
        try:
            repo = cls('.')
        except GitRepositoryError:
            raise SkipTest("Skipping '%s', since this is not a git checkout."
                           % __name__)

        submodules = repo.submodule_status()
        try:
            status = submodules[data]
        except KeyError:
            raise SkipTest("Skipping '%s', testdata directory not a known "
                           "submodule." % __name__)

        if status[0] == '-':
            raise SkipTest("Skipping '%s', testdata directory not initialized. "
                           "Consider doing 'git submodule update'" % __name__)


class ComponentTestBase(object):
    """Base class for testing cmdline tools of git-buildpackage"""

    @classmethod
    def setup_class(cls):
        """Test class case setup"""
        # Don't let git see that we're (possibly) under a git directory
        cls.orig_env = os.environ.copy()
        os.environ['GIT_CEILING_DIRECTORIES'] = os.getcwd()

    @classmethod
    def teardown_class(cls):
        """Test class case teardown"""
        # Return original environment
        os.environ.clear()
        os.environ.update(cls.orig_env)

    def __init__(self):
        """Object initialization"""
        self._orig_dir = None
        self._tmpdir = None
        self._log = None
        self._loghandler = None

    def setup(self):
        """Test case setup"""
        # Change to a temporary directory
        self._orig_dir = os.getcwd()
        self._tmpdir = tempfile.mkdtemp(prefix='gbp_%s_' % __name__, dir='.')
        os.chdir(self._tmpdir)

        self._capture_log(True)

    def teardown(self):
        """Test case teardown"""
        # Restore original working dir
        os.chdir(self._orig_dir)
        shutil.rmtree(self._tmpdir)

        self._capture_log(False)

    @classmethod
    def _check_repo_state(cls, repo, current_branch, branches, files=None):
        """Check that repository is clean and given branches exist"""
        branch = repo.branch
        assert branch == current_branch
        assert repo.is_clean()
        local_branches = repo.get_local_branches()
        assert_msg = "Branches: expected %s, found %s" % (branches,
                                                          local_branches)
        assert set(local_branches) == set(branches), assert_msg
        if files is not None:
            # Get files of the working copy recursively
            local = set()
            for dirpath, dirnames, filenames in os.walk(repo.path):
                # Skip git dir(s)
                if '.git' in dirnames:
                    dirnames.remove('.git')
                for filename in filenames:
                    local.add(os.path.relpath(os.path.join(dirpath, filename),
                                              repo.path))
                for dirname in dirnames:
                    local.add(os.path.relpath(os.path.join(dirpath, dirname),
                                              repo.path) + '/')
            extra = local - set(files)
            assert not extra, "Unexpected files in repo: %s" % list(extra)
            missing = set(files) - local
            assert not missing, "Files missing from repo: %s" % list(missing)

    def _capture_log(self, capture=True):
        """ Capture log"""
        if capture and self._log is None:
            self._log = StringIO()
            self._loghandler = gbp.log.GbpStreamHandler(self._log, False)
            self._loghandler.addFilter(gbp.log.GbpFilter([gbp.log.WARNING,
                                                          gbp.log.ERROR]))
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

    def _check_log(self, linenum, string):
        """Check that the specified line on log matches expectations"""
        if self._log is None:
            assert False, "BUG in unittests: no log captured!"
        output = self._get_log()[linenum].strip()
        assert output.startswith(string), ("Expected: '%s...' Got: '%s'" %
                                           (string, output))

    def _clear_log(self):
        """Clear the mock strerr"""
        if self._log is not None:
            self._log.seek(0)
            self._log.truncate()
