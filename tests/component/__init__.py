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
#    along with this program; if not, please see
#    <http://www.gnu.org/licenses/>
"""
Module for testing individual command line tools of the git-buildpackage suite
"""

import hashlib
import os
import shutil
import tempfile
import unittest
from unittest import skipUnless
from nose import SkipTest
from nose.tools import eq_, ok_     # pylint: disable=E0611
from .. testutils import GbpLogTester

from gbp.git import GitRepository, GitRepositoryError


__all__ = ['ComponentTestGitRepository', 'ComponentTestBase', 'GbpLogTester', 'skipUnless']


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

    def ls_tree(self, treeish):
        """List contents (blobs) in a git treeish"""
        objs = self.list_tree(treeish, True)
        blobs = [obj[3] for obj in objs if obj[1] == 'blob']
        return set(blobs)


class ComponentTestBase(unittest.TestCase, GbpLogTester):
    """Base class for testing cmdline tools of git-buildpackage"""

    @classmethod
    def setUpClass(cls):
        """Test class case setup"""
        # Don't let git see that we're (possibly) under a git directory
        cls.orig_env = os.environ.copy()
        os.environ['GIT_CEILING_DIRECTORIES'] = os.getcwd()
        # Create a top-level tmpdir for the test
        cls._tmproot = tempfile.mkdtemp(prefix='gbp_%s_' % cls.__name__,
                                        dir='.')
        cls._tmproot = os.path.abspath(cls._tmproot)
        # Prevent local config files from messing up the tests
        os.environ['GBP_CONF_FILES'] = ':'.join(['%(top_dir)s/.gbp.conf',
                                                 '%(top_dir)s/debian/gbp.conf',
                                                 '%(git_dir)s/gbp.conf'])

    @classmethod
    def tearDownClass(cls):
        """Test class case teardown"""
        # Return original environment
        os.environ.clear()
        os.environ.update(cls.orig_env)
        # Remove top-level tmpdir
        if not os.getenv("GBP_TESTS_NOCLEAN"):
            shutil.rmtree(cls._tmproot)

    def __init__(self, methodName='runTest'):
        """Object initialization"""
        self._orig_dir = None
        self._tmpdir = None
        unittest.TestCase.__init__(self, methodName)
        GbpLogTester.__init__(self)

    def setUp(self):
        """Test case setup"""
        # Change to a temporary directory
        self._orig_dir = os.getcwd()
        self._tmpdir = tempfile.mkdtemp(prefix='tmp_%s_' % self._testMethodName,
                                        dir=self._tmproot)
        os.chdir(self._tmpdir)

        self._capture_log(True)

    def tearDown(self):
        """Test case teardown"""
        # Restore original working dir
        os.chdir(self._orig_dir)
        if not os.getenv("GBP_TESTS_NOCLEAN"):
            shutil.rmtree(self._tmpdir)

        self._capture_log(False)

    @staticmethod
    def check_files(reference, filelist):
        """Compare two file lists"""
        extra = set(filelist) - set(reference)
        missing = set(reference) - set(filelist)
        assert_msg = "Unexpected files: %s, Missing files: %s" % \
                     (list(extra), list(missing))
        assert not extra and not missing, assert_msg

    @classmethod
    def check_tags(cls, repo, tags):
        local_tags = repo.tags
        assert_msg = "Tags: expected %s, found %s" % (tags,
                                                      local_tags)
        eq_(set(local_tags), set(tags), assert_msg)

    @classmethod
    def _check_repo_state(cls, repo, current_branch, branches, files=None,
                          dirs=None, tags=None):
        """
        Check that repository is clean and given branches, tags, files
        and dirs exist
        """
        branch = repo.branch
        eq_(branch, current_branch)
        ok_(repo.is_clean())
        local_branches = repo.get_local_branches()
        assert_msg = "Branches: expected %s, found %s" % (branches,
                                                          local_branches)
        eq_(set(local_branches), set(branches), assert_msg)

        if files is not None or dirs is not None:
            # Get files of the working copy recursively
            local_f = set()
            local_d = set()
            for dirpath, dirnames, filenames in os.walk(repo.path):
                # Skip git dir(s)
                if '.git' in dirnames:
                    dirnames.remove('.git')
                for filename in filenames:
                    local_f.add(os.path.relpath(os.path.join(dirpath, filename),
                                                repo.path))
                for dirname in dirnames:
                    local_d.add(os.path.relpath(os.path.join(dirpath, dirname),
                                                repo.path) + '/')
            if files is not None:
                cls.check_files(files, local_f)
            if dirs is not None:
                cls.check_files(dirs, local_d)
        if tags is not None:
            cls.check_tags(repo, tags)

    @classmethod
    def rem_refs(cls, repo, refs):
        """Remember the SHA1 of the given refs"""
        rem = []
        for name in refs:
            rem.append((name, repo.rev_parse(name)))
        return rem

    @classmethod
    def check_refs(cls, repo, rem):
        """
        Check that the heads given n (head, sha1) tuples are
        still pointing to the given sha1
        """
        for (h, s) in rem:
            n = repo.rev_parse(h)
            ok_(n == s, "Head '%s' points to %s' instead of '%s'" % (h, n, s))

    @staticmethod
    def hash_file(filename):
        h = hashlib.md5()
        with open(filename, 'rb') as f:
            buf = f.read()
            h.update(buf)
        return h.hexdigest()

    @staticmethod
    def check_hook_vars(name, expected):
        """
        Check that a hook had the given vars in
        it's environment.
        This assumes the hook was set too
            printenv > hookname.out
        """
        with open('%s.out' % name) as f:
            parsed = dict([line[:-1].split('=', 1) for line in f.readlines() if line.startswith("GBP_")])

        for var in expected:
            if len(var) == 2:
                k, v = var
            else:
                k, v = var, None
            ok_(k in parsed, "%s not found in %s" % (k, parsed))
            if v is not None:
                ok_(v == parsed[k],
                    "Got %s not expected value %s for %s" % (parsed[k], v, k))
