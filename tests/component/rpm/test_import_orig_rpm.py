# vim: set fileencoding=utf-8 :
#
# (C) 2012-2015 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""Test importing RPMs with git-import-orig"""

import os
import shutil
import sys
import subprocess
from nose.tools import eq_
from io import StringIO

from gbp.scripts.import_orig import main as import_orig

from tests.component import ComponentTestBase, ComponentTestGitRepository
from tests.component.rpm import RPM_TEST_DATA_DIR

# Disable "Method could be a function warning"
# pylint: disable=R0201

DATA_DIR = os.path.join(RPM_TEST_DATA_DIR, 'orig')


def mock_import(args, stdin_data="\n\n", cwd=None):
    """Wrapper for import-orig for feeding mock stdin data to it"""
    old_cwd = os.path.abspath(os.path.curdir)
    if cwd:
        os.chdir(cwd)

    # Create stub file with mock data
    mock_stdin = StringIO()
    mock_stdin.write(stdin_data)
    mock_stdin.seek(0)

    # Call import-orig-rpm with mock data
    sys.stdin = mock_stdin
    ret = import_orig(['arg0'] + args)
    sys.stdin = sys.__stdin__
    mock_stdin.close()

    # Return to original working directory
    if cwd:
        os.chdir(old_cwd)
    return ret


class ImportOrigTestBase(ComponentTestBase):
    """Base class for all import-orig-rpm unit tests"""

    @classmethod
    def setUpClass(cls):
        """Class setup, common for all test cases"""
        super(ImportOrigTestBase, cls).setUpClass()

    def __init__(self, *args, **kwargs):
        super(ImportOrigTestBase, self).__init__(*args, **kwargs)

    def setUp(self):
        """Test case setup"""
        super(ImportOrigTestBase, self).setUp()

    @classmethod
    def check_tree(cls, repo, treeish, filelist):
        """Check the contents (list of files) in a git treeish"""
        treeish_files = repo.ls_tree(treeish)
        ImportOrigTestBase.check_files(treeish_files, filelist)


class TestImportOrig(ImportOrigTestBase):
    """Basic tests for git-import-orig-rpm"""

    def test_invalid_args(self):
        """
        See that import-orig-rpm fails gracefully when called with invalid args
        """
        repo = ComponentTestGitRepository.create('.')
        origs = [os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2'),
                 os.path.join(DATA_DIR, 'gbp-test-1.1.tar.bz2')]
        # Test empty args
        eq_(mock_import([]), 1)
        self._clear_log()

        # Test multiple archives
        eq_(mock_import([] + origs), 1)
        self._check_log(0, 'gbp:error: More than one archive specified')
        self._clear_log()

        # Check that nothing is in the repo
        self._check_repo_state(repo, None, [])

    def test_import_outside_repo(self):
        """Test importing when not in a git repository"""
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        # Import should fail
        eq_(mock_import([orig]), 1)
        self._check_log(0, 'gbp:error: %s is not a git repository' %
                        os.path.abspath(os.getcwd()))

    def test_invalid_config_file(self):
        """Test invalid config file"""
        # Create dummy invalid config file and try to import (should fail)
        ComponentTestGitRepository.create('.')
        with open('.gbp.conf', 'w') as conffd:
            conffd.write('foobar\n')
        eq_(mock_import(['foo']), 3)
        self._check_log(0, 'gbp:error: File contains no section headers.')

    def test_import_tars(self):
        """Test importing of tarballs, with and without merging"""
        repo = ComponentTestGitRepository.create('.')
        # Import first version, with --merge
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(mock_import(['--merge', orig]), 0)
        files = ['Makefile', 'README', 'dummy.sh']
        self._check_repo_state(repo, 'master', ['master', 'upstream'], files)
        eq_(len(repo.get_commits(until='master')), 1)
        eq_(len(repo.get_commits(until='upstream')), 1)
        eq_(repo.get_tags(), ['upstream/1.0'])

        # Import second version, don't merge to master branch
        orig = os.path.join(DATA_DIR, 'gbp-test-1.1.tar.bz2')
        eq_(mock_import(['--no-merge', orig]), 0)
        self._check_repo_state(repo, 'master', ['master', 'upstream'], files)
        eq_(len(repo.get_commits(until='master')), 1)
        eq_(len(repo.get_commits(until='upstream')), 2)
        eq_(repo.get_tags(), ['upstream/1.0', 'upstream/1.1'])
        # Check that master is based on v1.0
        sha1 = repo.rev_parse("%s^0" % 'upstream/1.0')
        eq_(repo.get_merge_base('master', 'upstream'), sha1)

    def test_import_zip(self):
        """Test importing of zip archive"""
        repo = ComponentTestGitRepository.create('.')
        # Import zip with, no master branch should be present
        orig = os.path.join(DATA_DIR, 'gbp-test-native-1.0.zip')
        files = ['.gbp.conf', 'packaging/gbp-test-native.spec',
                 'dummy.sh', 'README', 'Makefile']
        eq_(mock_import([orig]), 0)
        self._check_repo_state(repo, 'master', ['master', 'upstream'], files)
        eq_(repo.get_tags(), ['upstream/1.0'])

    def test_branch_update(self):
        """Check that the working copy is kept in sync with branch HEAD"""
        repo = ComponentTestGitRepository.create('.')
        orig1 = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        orig2 = os.path.join(DATA_DIR, 'gbp-test-1.1.tar.bz2')
        eq_(mock_import(['--merge', orig1]), 0)
        repo.set_branch('upstream')
        eq_(mock_import([orig2]), 0)
        files = ['Makefile', 'README', 'dummy.sh']
        self._check_repo_state(repo, 'upstream', ['master', 'upstream'], files)
        eq_(len(repo.get_commits(until='upstream')), 2)

    def test_import_dir(self):
        """Test importing of unpacked sources"""
        # Unpack sources and create repo
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        subprocess.Popen(['tar', 'xf', orig])
        repo = ComponentTestGitRepository.create('myrepo')
        os.chdir('myrepo')

        # Import dir first, fool the version to be 0.9
        eq_(mock_import(['../gbp-test'], 'gbp-test\n0.9\n'), 0)
        files = ['Makefile', 'README', 'dummy.sh']
        self._check_repo_state(repo, 'master', ['master', 'upstream'], files)

        # Import from unpacked and check that the contents is the same
        eq_(mock_import([orig]), 0)
        eq_(len(repo.diff('upstream/0.9', 'upstream/1.0')), 0)

    def test_basic_filtering(self):
        """Basic test for import filter"""
        repo = ComponentTestGitRepository.create('.')
        orig = os.path.join(DATA_DIR, 'gbp-test-1.1.with_dotgit.tar.bz2')
        # Try importing a tarball with git metadata
        eq_(mock_import([orig], 'gbp-test\n1.0\n'), 1)
        self._check_log(0, 'gbp:error: The orig tarball contains .git')

        # Try filtering out .git directory and shell scripts
        eq_(mock_import(['--filter=.git', '--filter=*.sh', '--merge', orig],
                        'gbp-test\n1.0\n'), 0)
        self._check_repo_state(repo, 'master', ['master', 'upstream'])
        eq_(len(repo.get_commits(until='master')), 1)
        eq_(len(repo.get_commits(until='upstream')), 1)
        eq_(repo.get_tags(), ['upstream/1.0'])
        added_files = repo.get_commit_info('upstream')['files']['A']
        eq_(set(added_files), set([b'Makefile', b'README']))

    def test_noninteractive(self):
        """Test non-interactive mode"""
        repo = ComponentTestGitRepository.create('testrepo')
        orig = os.path.join(DATA_DIR, 'gbp-test-native-1.0.zip')
        orig_renamed = os.path.join(os.path.abspath('.'), 'foo.zip')
        shutil.copy(orig, orig_renamed)
        os.chdir('testrepo')

        # Guessing name and version should fail
        eq_(mock_import(['--no-interactive', orig_renamed]), 1)
        self._check_log(-1, "gbp:error: Couldn't determine upstream package")

        # Guessing from the original archive should succeed
        eq_(mock_import(['--no-interactive', '--merge', orig],
                        stdin_data=''), 0)
        files = ['.gbp.conf', 'Makefile', 'README', 'dummy.sh',
                 'packaging/gbp-test-native.spec']
        self._check_repo_state(repo, 'master', ['master', 'upstream'], files)
        eq_(len(repo.get_commits(until='master')), 1)

    def test_misc_options(self):
        """Test various options of git-import-orig-rpm"""
        repo = ComponentTestGitRepository.create('.')
        # Force --no-ff for merges because default behavior is slightly
        # different in newer git versions (> 2.16)
        repo.set_config("branch.pack.mergeoptions", "--no-ff")

        # Import one orig with default options to get upstream and
        # packaging branch
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(mock_import(['--debian-branch=pack',
                         '--upstream-branch=orig', '-u0.8', orig]), 0)
        self._check_repo_state(repo, 'pack', ['pack', 'orig'])

        # Import the "native" zip to get packaging files
        orig = os.path.join(DATA_DIR, 'gbp-test-native-1.0.zip')
        base_args = ['--debian-branch=pack', '--upstream-branch=orig',
                     '--upstream-tag=orig/%(version)s', '--merge']
        # Fake version to be 0.9
        extra_args = ['-u0.9', '--upstream-vcs-tag=upstream/0.8', orig]
        eq_(mock_import(base_args + extra_args), 0)
        # Check repository state
        files = ['dummy.sh', 'packaging/gbp-test-native.spec',
                 '.gbp.conf', 'Makefile', 'README']
        self._check_repo_state(repo, 'pack', ['pack', 'orig'], files)
        eq_(len(repo.get_commits(until='pack')), 3)
        # Check tags
        tags = repo.get_tags()
        eq_(set(tags), set(['upstream/0.8', 'orig/0.9']))

        # Change to packaging branch and create new commit
        repo.set_branch('pack')
        shutil.copy2('.git/HEAD', 'my_new_file')
        repo.add_files('.')
        repo.commit_all('My new commit')
        # Import a new version, name should be taken from spec
        orig = os.path.join(DATA_DIR, 'gbp-test-1.1.tar.bz2')
        extra_args = ['--no-interactive', '-u1.1', orig]
        eq_(mock_import(base_args + extra_args, ''), 0)
        # Threeupstream versions, "my new" commit and one merge commit
        eq_(len(repo.get_commits(until='pack')), 6)
        tags = repo.get_tags()
        eq_(set(tags), set(['upstream/0.8', 'orig/0.9', 'orig/1.1']))

    def test_import_hooks(self):
        """Basic test for postimport hook"""
        repo = ComponentTestGitRepository.create('.')
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')

        script = ("echo -n branch: $GBP_BRANCH > ../hook.txt")
        eq_(mock_import(['--postimport', script, '--merge', orig]), 0)
        self._check_repo_state(repo, 'master', ['master', 'upstream'])
        eq_(repo.get_tags(), ['upstream/1.0'])
        with open('../hook.txt', 'r') as hookout:
            data = hookout.read()
        eq_(data, 'branch: master')

    def test_hook_error(self):
        """Test postimport hook failure"""
        repo = ComponentTestGitRepository.create('.')
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(mock_import(['--postimport=/bin/false', '--merge', '--no-rollback', orig]), 1)
        self._check_log(-2, "gbp:error: Postimport-hook '/bin/false' failed:")
        self._check_log(-1, 'gbp:error: Import of %s failed' % orig)
        # Other parts of the import should've succeeded
        self._check_repo_state(repo, 'master', ['master', 'upstream'])


class TestBareRepo(ImportOrigTestBase):
    """Test importing to a bare repository"""

    def test_basic_import_to_bare_repo(self):
        """Test importing inside bare git repository"""
        repo = ComponentTestGitRepository.create('.', bare=True)
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(mock_import([orig]), 0)
        self._check_repo_state(repo, 'master', ['master', 'upstream'])
        eq_(len(repo.get_commits(until='upstream')), 1)
        eq_(repo.get_tags(), ['upstream/1.0'])

        # Import another version
        repo.set_branch('upstream')
        orig = os.path.join(DATA_DIR, 'gbp-test-1.1.tar.bz2')
        eq_(mock_import([orig]), 0)
        self._check_repo_state(repo, 'upstream', ['master', 'upstream'])
        eq_(len(repo.get_commits(until='upstream')), 2)

    def test_pristine_import_to_bare(self):
        """Test importing inside bare git repository"""
        repo = ComponentTestGitRepository.create('.', bare=True)
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(mock_import([orig]), 0)
        # No pristine-tar branch should be present
        self._check_repo_state(repo, 'master', ['master', 'upstream'])
