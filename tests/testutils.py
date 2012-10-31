# vim: set fileencoding=utf-8 :

import os
import shutil
import tempfile
import unittest
from StringIO import StringIO

import gbp.log
import gbp.deb.git
import gbp.errors

class DebianGitTestRepo(unittest.TestCase):
    """Scratch repo for a single test"""

    def setUp(self):
        gbp.log.setup(False, False)
        top = os.path.abspath(os.path.curdir)
        self.tmpdir = os.path.join(top, 'gbp_%s_repo' % __name__)
        os.mkdir(self.tmpdir)

        repodir = os.path.join(self.tmpdir, 'test_repo')
        self.repo = gbp.deb.git.DebianGitRepository.create(repodir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

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

        with file(path, 'w+') as f:
            content == None or f.write(content)
        self.repo.add_files(name, force=True)
        self.repo.commit_files(path, msg or "added %s" % name)


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
        os.environ = cls.orig_env

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
    def _check_repo_state(cls, repo, current_branch, branches):
        """Check that repository is clean and given branches exist"""
        branch = repo.branch
        assert branch == current_branch
        assert repo.is_clean()
        assert set(repo.get_local_branches()) == set(branches)

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

