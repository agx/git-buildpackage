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
"""Tests for the git-import-orig-rpm tool"""

import os
import shutil
import sys
import subprocess
import tarfile
import tempfile
from nose.plugins.skip import SkipTest
from nose.tools import assert_raises, eq_   # pylint: disable=E0611
from StringIO import StringIO

from gbp.scripts.import_orig_rpm import main as import_orig_rpm

from tests.testutils import ls_dir, ls_tar, ls_zip
from tests.component import ComponentTestBase, ComponentTestGitRepository
from tests.component.rpm import RPM_TEST_DATA_DIR

# Disable "Method could be a function warning"
# pylint: disable=R0201

DATA_DIR = os.path.join(RPM_TEST_DATA_DIR, 'orig')


def mock_import(args, stdin_data="\n\n", cwd=None):
    """Wrapper for import-orig-rpm for feeding mock stdin data to it"""
    old_cwd = os.path.abspath(os.path.curdir)
    if cwd:
        os.chdir(cwd)

    # Create stub file with mock data
    mock_stdin = StringIO()
    mock_stdin.write(stdin_data)
    mock_stdin.seek(0)

    # Call import-orig-rpm with mock data
    sys.stdin = mock_stdin
    ret = import_orig_rpm(['arg0'] + args)
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

        # Test invalid archive
        false_orig = os.path.join(RPM_TEST_DATA_DIR, 'gbp-test-1.0-1.src.rpm')
        eq_(mock_import([false_orig], 'foo\n1\n'), 1)
        self._check_log(0, "gbp:error: Unsupported archive format")
        self._clear_log()

        # Test non-existing archive
        eq_(mock_import(['none.tar.bz2'], 'foo\n1\n'), 1)
        self._check_log(0, "gbp:error: UpstreamSource: unable to find")
        self._clear_log()

        # Check that nothing is in the repo
        self._check_repo_state(repo, None, [])

        # Test invalid cmdline options
        with assert_raises(SystemExit):
            mock_import(['--invalid-arg=123'])

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
        eq_(mock_import(['foo']), 1)
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
        eq_(mock_import([orig]), 0)
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
        eq_(mock_import([orig]), 0)
        self._check_repo_state(repo, None, ['upstream'], [])
        eq_(repo.get_tags(), ['upstream/1.0'])

    def test_import_to_existing(self):
        """Test importing of to an existing repo"""
        # Create new repo and add dummy files
        repo = ComponentTestGitRepository.create('.')
        shutil.copy2('.git/HEAD', 'foobar')
        repo.add_files('.')
        repo.commit_all('First commit')
        sha1 = repo.rev_parse('HEAD^0')

        # Test missing upstream branch
        orig = os.path.join(DATA_DIR, 'gbp-test2-2.0.tar.gz')
        eq_(mock_import([orig]), 1)
        self._check_log(1, 'Repository does not have branch')

        # Create orphan, empty, 'usptream' branch
        tree = repo.write_tree('.git/_empty_index')
        commit = repo.commit_tree(tree=tree, msg='Initial upstream', parents=[])
        repo.update_ref("refs/heads/upstream", commit)

        # Test importing to non-clean repo
        files = ['foobar']
        self._check_repo_state(repo, 'master', ['master', 'upstream'], files)
        shutil.copy2('.git/HEAD', 'foobaz')
        self._clear_log()
        eq_(mock_import([orig]), 1)
        self._check_log(0, 'gbp:error: Repository has uncommitted changes')
        os.unlink('foobaz')

        # Create new branch
        repo.create_branch('mytopic')
        repo.set_branch('mytopic')

        # Finally, import should succeed
        eq_(mock_import([orig, '--merge']), 0)
        files = ['Makefile', 'README', 'dummy.sh', 'foobar']
        self._check_repo_state(repo, 'master',
                               ['master', 'mytopic', 'upstream'], files)
        eq_(repo.get_tags(), ['upstream/2.0'])
        # Our topic branch shouldn't have changed, unlike master
        eq_(repo.rev_parse('mytopic^0'), sha1)
        eq_(len(repo.get_commits(until='mytopic')), 1)
        # One commit from topic branch, two from upstream, one merge commit
        eq_(len(repo.get_commits(until='master')), 4)

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
        self.check_tree(repo, 'upstream', files)
        self._check_repo_state(repo, None, ['upstream'], [])

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
        eq_(set(added_files), set(['Makefile', 'README']))

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

        # Import "new" version, this time package name should be taken from spec
        eq_(mock_import(['--no-interactive', orig_renamed], stdin_data=''), 1)
        self._check_log(-1, "gbp:error: Couldn't determine upstream version")

    def test_misc_options(self):
        """Test various options of git-import-orig-rpm"""
        repo = ComponentTestGitRepository.create('.')
        # Import one orig with default options to get 'upstream' branch
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(mock_import(['-u0.8', orig]), 0)

        # Import the "native" zip to get packaging files
        orig = os.path.join(DATA_DIR, 'gbp-test-native-1.0.zip')
        base_args = ['--packaging-branch=pack', '--upstream-branch=orig',
                     '--upstream-tag=orig/%(upstreamversion)s', '--merge']
        # Fake version to be 0.9
        extra_args = ['-u0.9', '--upstream-vcs-tag=upstream/0.8', orig]
        eq_(mock_import(base_args + extra_args), 0)
        # Check repository state
        files = []
        self._check_repo_state(repo, None, ['pack', 'orig', 'upstream'], files)
        eq_(len(repo.get_commits(until='pack')), 2)
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
        extra_args = ['--packaging-dir=packaging', '--no-interactive', '-u1.1',
                      orig]
        eq_(mock_import(base_args + extra_args, ''), 0)
        # Threeupstream versions, "my new" commit and one merge commit
        eq_(len(repo.get_commits(until='pack')), 5)
        tags = repo.get_tags()
        eq_(set(tags), set(['upstream/0.8', 'orig/0.9', 'orig/1.1']))

    def test_import_hooks(self):
        """Basic test for postimport hook"""
        repo = ComponentTestGitRepository.create('.')
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')

        script = ("echo -n branch: $GBP_BRANCH, version: %(upstreamversion)s"
                  " > hook.txt")
        eq_(mock_import(['--postimport', script, '--merge', orig]), 0)
        self._check_repo_state(repo, 'master', ['master', 'upstream'])
        eq_(repo.get_tags(), ['upstream/1.0'])
        with open('hook.txt', 'r') as hookout:
            data = hookout.read()
        eq_(data, 'branch: master, version: 1.0')

    def test_hook_error(self):
        """Test postimport hook failure"""
        repo = ComponentTestGitRepository.create('.')
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(mock_import(['--postimport=_notexist.sh', '--merge', orig]), 1)
        self._check_log(-2, "gbp:error: '_notexist.sh' failed:")
        self._check_log(-1, 'gbp:error: Import of %s failed' % orig)
        # Other parts of the import should've succeeded
        self._check_repo_state(repo, 'master', ['master', 'upstream'])


class TestPristineTar(ImportOrigTestBase):
    """
    Test importing with pristine-tar

    Especially, tests different options for mangling the tarball. We basically
    have these mostly independent options:
        - filter
        - filter-pristine-tar
        - pristine-tarball-name
        - orig-prefix
    And, these options can be used in importing directories and tarballs and zip
    files.
    """

    @classmethod
    def setUpClass(cls):
        """Class setup, common for all test cases"""
        if not os.path.exists('/usr/bin/pristine-tar'):
            raise SkipTest('Skipping %s:%s as pristine-tar tool is not '
                           'available' % (__name__, cls.__name__))
        super(TestPristineTar, cls).setUpClass()

    def __init__(self, *args, **kwargs):
        super(TestPristineTar, self).__init__(*args, **kwargs)
        self.repo = None

    def setUp(self):
        """Test case setup"""
        super(TestPristineTar, self).setUp()
        self.repo = ComponentTestGitRepository.create('repo')

    def check_repo(self, current_branch, branches=None, files=None):
        """Check the state of repo"""
        if branches is None:
            # Default branches
            branches =  ['upstream', 'pristine-tar']
        return self._check_repo_state(self.repo, current_branch, branches,
                                      files)

    def check_tree(self, treeish, filelist):
        """Check treeish content"""
        return super(TestPristineTar, self).check_tree(self.repo, treeish,
                                                       filelist)

    @staticmethod
    def unpack_tar(archive):
        """Unpack tarball, return directory containing sources"""
        tarobj = tarfile.open(archive, 'r')
        os.mkdir('unpacked')
        tarobj.extractall('unpacked')
        tarobj.close()
        dirlist = os.listdir('unpacked')
        if len(dirlist) == 1:
            return os.path.abspath(os.path.join('unpacked', dirlist[0]))
        else:
            return os.path.abspath('unpacked')

    def mock_import(self, args, stdin_data="\n\n"):
        """Import helper for pristine-tar"""
        return mock_import(args, stdin_data, self.repo.path)

    def ls_pristine_tar(self, archive):
        """List contents of the tarball committed into pristine-tar"""
        tmpdir = os.path.abspath(tempfile.mkdtemp(dir='.'))
        tarball = os.path.join(tmpdir, archive)
        try:
            popen = subprocess.Popen(['pristine-tar', 'checkout', tarball],
                                     cwd=self.repo.path)
            popen.wait()
            if popen.returncode:
                raise Exception('Pristine-tar checkout failed!')
            return ls_tar(tarball)
        finally:
            shutil.rmtree(tmpdir)

    def test_basic_import_pristine_tar(self):
        """Test importing with pristine-tar"""
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(self.mock_import(['--pristine-tar', '--merge', orig]), 0)
        files = ['Makefile', 'README', 'dummy.sh']
        branches = ['master', 'upstream', 'pristine-tar']
        self.check_repo('master', branches, files)
        subject = self.repo.get_commit_info('pristine-tar')['subject']
        eq_(subject, 'pristine-tar data for %s' % os.path.basename(orig))
        self.check_files(ls_tar(orig),
                         self.ls_pristine_tar('gbp-test-1.0.tar.bz2'))

    def test_rename(self):
        """Renaming orig archive"""
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        args = ['--pristine-tar', '--pristine-tarball-name=my.tgz', orig]
        eq_(self.mock_import(args), 0)
        self.check_repo(None, None, [])
        self.check_files(ls_tar(orig), self.ls_pristine_tar('my.tgz'))

    def test_branch_update(self):
        """Check that the working copy is kept in sync with branch HEAD"""
        orig1 = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        orig2 = os.path.join(DATA_DIR, 'gbp-test-1.1.tar.bz2')
        eq_(self.mock_import(['--pristine-tar', orig1]), 0)
        self.repo.set_branch('pristine-tar')
        eq_(self.mock_import(['--pristine-tar', orig2]), 0)
        self.check_repo('pristine-tar', None)
        eq_(len(self.repo.get_commits(until='pristine-tar')), 2)

    def test_zip(self):
        """Importing zip file"""
        orig = os.path.join(DATA_DIR, 'gbp-test-native-1.0.zip')
        eq_(self.mock_import(['--pristine-tar', orig]), 0)
        files = ['.gbp.conf', 'Makefile', 'README', 'dummy.sh',
                 'packaging/gbp-test-native.spec']
        self.check_repo(None, None, [])
        self.check_tree('upstream', files)
        self.check_files(ls_zip(orig),
                         self.ls_pristine_tar('gbp-test-native-1.0.tar.gz'))

#{ Test tarball mangling
    def test_nopristinefilter(self):
        """Test --no-pristine-tar-filter"""
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(self.mock_import(['--pristine-tar', '--filter=README', orig]), 0)
        self.check_repo(None, None, [])
        self.check_tree('upstream', ['Makefile', 'dummy.sh'])
        self.check_files(ls_tar(orig),
                         self.ls_pristine_tar('gbp-test-1.0.tar.bz2'))

    def test_nofilter_prefix(self):
        """Test prefix mangling without any filtering"""
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(self.mock_import(['--pristine-tar', '--orig-prefix=new', orig]), 0)
        self.check_repo(None, None, None)
        self.check_tree('upstream', ['Makefile', 'dummy.sh', 'README'])
        prist_ref = set([fname.replace('gbp-test', 'new') for
                            fname in ls_tar(orig)])
        self.check_files(prist_ref,
                         self.ls_pristine_tar('gbp-test-1.0.tar.bz2'))

    def test_nopristinefilter_prefix(self):
        """Test --no-pristine-tar-filter with prefix mangling"""
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        args = ['--pristine-tar', '--filter=README', '--orig-prefix=new', orig]
        eq_(self.mock_import(args), 0)
        self.check_repo(None, None, None)
        self.check_tree('upstream', ['Makefile', 'dummy.sh'])
        prist_ref = set([fname.replace('gbp-test', 'new') for
                            fname in ls_tar(orig)])
        self.check_files(prist_ref,
                         self.ls_pristine_tar('gbp-test-1.0.tar.bz2'))

    def test_filter_prefix_rename(self):
        """Test --no-pristine-tar-filter with prefix mangling"""
        orig = os.path.join(DATA_DIR, 'gbp-test2-2.0.tar.gz')
        args = ['--pristine-tar', '--filter=README', '--orig-prefix=new',
                '--pristine-tarball-name=new.tbz2', '--filter-pristine-tar',
                orig]
        eq_(self.mock_import(args), 0)
        self.check_repo(None, None, [])
        self.check_tree('upstream', ['Makefile', 'dummy.sh'])
        prist_ref = set(['new', 'new/Makefile', 'new/dummy.sh'])
        self.check_files(prist_ref, self.ls_pristine_tar('new.tbz2'))

    def test_dir_nopristinefilter(self):
        """Test importing directory with --no-pristine-tar-filter"""
        orig = self.unpack_tar(os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2'))
        args = ['--pristine-tar', '--filter=README', orig]
        eq_(self.mock_import(args, 'gbp-test\n1.0\n'), 0)
        files = ['Makefile', 'dummy.sh']
        self.check_repo(None, None, [])
        self.check_tree('upstream', ['Makefile', 'dummy.sh'])
        prist_ref = set(['gbp-test-1.0/%s' % fname for fname in ls_dir(orig)] +
                        ['gbp-test-1.0'])
        self.check_files(prist_ref, self.ls_pristine_tar('gbp-test.tar.gz'))

    def test_dir_filter_prefix(self):
        """Test importing directory with prefix mangling"""
        orig = self.unpack_tar(os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2'))
        args = ['--pristine-tar', '--filter=README', '--filter-pristine-tar',
                '--orig-prefix=', '--pristine-tarball-name=my.tgz', orig]
        eq_(self.mock_import(args, 'gbp-test\n1.0\n'), 0)
        files = ['Makefile', 'dummy.sh']
        self.check_repo(None, None, [])
        self.check_tree('upstream', files)
        self.check_files(set(files), self.ls_pristine_tar('my.tgz'))


class TestBareRepo(ImportOrigTestBase):
    """Test importing to a bare repository"""

    def test_basic_import_to_bare_repo(self):
        """Test importing inside bare git repository"""
        repo = ComponentTestGitRepository.create('.', bare=True)
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(mock_import([orig]), 0)
        self._check_repo_state(repo, None, ['upstream'])
        eq_(len(repo.get_commits(until='upstream')), 1)
        eq_(repo.get_tags(), ['upstream/1.0'])

        # Import another version
        repo.set_branch('upstream')
        orig = os.path.join(DATA_DIR, 'gbp-test-1.1.tar.bz2')
        eq_(mock_import([orig]), 0)
        self._check_repo_state(repo, 'upstream', ['upstream'])
        eq_(len(repo.get_commits(until='upstream')), 2)

    def test_pristine_import_to_bare(self):
        """Test importing inside bare git repository"""
        repo = ComponentTestGitRepository.create('.', bare=True)
        orig = os.path.join(DATA_DIR, 'gbp-test-1.0.tar.bz2')
        eq_(mock_import([orig]), 0)
        # No pristine-tar branch should be present
        self._check_repo_state(repo, None, ['upstream'])

