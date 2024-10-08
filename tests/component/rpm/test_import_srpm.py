# vim: set fileencoding=utf-8 :
#
# (C) 2012 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""Basic tests for the git-import-srpm tool"""

import os
import shutil
import urllib
from unittest.mock import Mock

import pytest

import gbp.scripts.import_srpm as import_srpm
from gbp.git import GitRepository
from gbp.rpm import SrcRpmFile

from tests.component import ComponentTestBase
from tests.component.rpm import RPM_TEST_DATA_DIR as DATA_DIR
from tests.testutils import capture_stderr

# Disable "Method could be a function warning"
# pylint: disable=R0201


def mock_import(args):
    """Wrapper for import-srpm"""
    # Call import-orig-rpm with added arg0
    with capture_stderr():
        return import_srpm.main(['arg0'] + args)


class TestImportPacked(ComponentTestBase):
    """Test importing of src.rpm files"""

    def test_invalid_args(self):
        """See that import-srpm fails gracefully if called with invalid args"""
        assert mock_import([]) == 1
        with pytest.raises(SystemExit):
            mock_import(['--invalid-arg=123'])

    def test_basic_import(self):
        """Test importing of non-native src.rpm"""
        srpm = os.path.join(DATA_DIR, "gbp-test-1.0-1.src.rpm")
        assert mock_import(["--no-pristine-tar", srpm]) == 0
        # Check repository state
        repo = GitRepository('gbp-test')
        files = {'Makefile', 'README', 'bar.tar.gz', 'dummy.sh', 'foo.txt',
                 'gbp-test.spec', 'my.patch', 'my2.patch', 'my3.patch'}
        self._check_repo_state(repo, 'master', ['master', 'upstream'],
                               files=files,
                               tags=['packaging/1.0-1', 'upstream/1.0'])
        # Two commits: upstream and packaging files
        assert len(repo.get_commits()) == 2

    def test_basic_import2(self):
        """Import package with multiple spec files and full url patch"""
        srpm = os.path.join(DATA_DIR, "gbp-test2-2.0-0.src.rpm")
        assert mock_import(["--no-pristine-tar", srpm]) == 0
        # Check repository state
        repo = GitRepository('gbp-test2')
        files = {'Makefile', 'README', 'bar.tar.gz', 'dummy.sh', 'foo.txt',
                 'gbp-test2.spec', 'gbp-test2-alt.spec', 'my.patch',
                 'my2.patch', 'my3.patch'}
        self._check_repo_state(repo, 'master', ['master', 'upstream'],
                               files=files,
                               tags=['packaging/1%2.0-0', 'upstream/2.0'])
        # Two commits: upstream and packaging files
        assert len(repo.get_commits()) == 2

    def test_target_dir(self):
        """Test importing to target dir"""
        srpm = os.path.join(DATA_DIR, "gbp-test-1.0-1.src.rpm")
        assert mock_import(["--no-pristine-tar", srpm, "targetdir"]) == 0
        # Check repository state
        assert os.path.exists('targetdir')
        repo = GitRepository('targetdir')
        self._check_repo_state(repo, 'master', ['master', 'upstream'])

    def test_basic_import_orphan(self):
        """
        Test importing of non-native src.rpm to separate packaging and
        development branches
        """
        srpm = os.path.join(DATA_DIR, "gbp-test2-2.0-0.src.rpm")
        assert mock_import(["--no-pristine-tar", "--orphan-packaging", srpm]) == 0
        # Check repository state
        repo = GitRepository('gbp-test2')
        files = {'bar.tar.gz', 'foo.txt', 'gbp-test2.spec',
                 'gbp-test2-alt.spec', 'my.patch', 'my2.patch', 'my3.patch'}
        self._check_repo_state(repo, 'master', ['master', 'upstream'], files)
        # Only one commit: the packaging files
        assert len(repo.get_commits()) == 1

    def test_basic_native_import(self):
        """Test importing of native src.rpm"""
        srpm = os.path.join(DATA_DIR, "gbp-test-native-1.0-1.src.rpm")
        assert mock_import(["--native", srpm]) == 0
        # Check repository state
        files = {'.gbp.conf', 'Makefile', 'README', 'dummy.sh',
                 'packaging/gbp-test-native.spec'}
        repo = GitRepository('gbp-test-native')
        self._check_repo_state(repo, 'master', ['master'],
                               files=files,
                               tags=['packaging/1.0-1'])
        # Only one commit: the imported source tarball
        assert len(repo.get_commits()) == 1

    def test_import_no_orig_src(self):
        """Test importing of (native) srpm without orig tarball"""
        srpm = os.path.join(DATA_DIR, 'gbp-test-native2-2.0-0.src.rpm')
        assert mock_import([srpm]) == 0
        # Check repository state
        repo = GitRepository('gbp-test-native2')
        self._check_repo_state(repo, 'master', ['master'])
        # Only one commit: packaging files
        assert len(repo.get_commits()) == 1

    def test_multiple_versions(self):
        """Test importing of multiple versions"""
        srpms = [
            os.path.join(DATA_DIR, x)
            for x in [
                "gbp-test-1.0-1.src.rpm",
                "gbp-test-1.0-1.other.src.rpm",
                "gbp-test-1.1-1.src.rpm",
            ]
        ]
        assert mock_import(["--no-pristine-tar", srpms[0]]) == 0
        repo = GitRepository("gbp-test")
        self._check_repo_state(repo, "master", ["master", "upstream"])
        assert len(repo.get_commits()) == 2
        # Try to import same version again
        assert mock_import([srpms[1]]) == 0
        assert len(repo.get_commits()) == 2
        assert len(repo.get_commits(until="upstream")) == 1
        assert mock_import(["--no-pristine-tar", "--allow-same-version", srpms[1]]) == 0
        # Added new version of packaging
        assert len(repo.get_commits()) == 3
        assert len(repo.get_commits(until="upstream")) == 1
        # Import new version
        assert mock_import(["--no-pristine-tar", srpms[2]]) == 0
        files = {
            "Makefile",
            "README",
            "bar.tar.gz",
            "dummy.sh",
            "foo.txt",
            "gbp-test.spec",
            "my.patch",
            "my2.patch",
            "my3.patch",
        }
        self._check_repo_state(repo, "master", ["master", "upstream"], files)
        assert len(repo.get_commits()) == 5
        assert len(repo.get_commits(until="upstream")) == 2
        # Check number of tags
        assert len(repo.get_tags("upstream/*")) == 2
        assert len(repo.get_tags("packaging/*")) == 3

    def test_import_to_existing(self):
        """Test importing to an existing repo"""
        srpm = os.path.join(DATA_DIR, 'gbp-test-1.0-1.src.rpm')

        # Create new repo
        repo = GitRepository.create('myrepo')
        os.chdir('myrepo')
        shutil.copy2('.git/HEAD', 'foobar')
        repo.add_files('.')
        repo.commit_all('First commit')

        # Test importing to non-clean repo
        shutil.copy2(".git/HEAD", "foobaz")
        assert mock_import(["--create-missing", srpm]) == 1
        self._check_log(0, "gbp:error: Repository has uncommitted changes")
        self._clear_log()
        os.unlink('foobaz')

        # The first import should fail because upstream branch is missing
        assert mock_import([srpm]) == 1
        self._check_log(-1, "Also check the --create-missing-branches")
        assert mock_import(["--no-pristine-tar", "--create-missing", srpm]) == 0
        self._check_repo_state(repo, "master", ["master", "upstream"])
        # Four commits: our initial, upstream and packaging files
        assert len(repo.get_commits()) == 3

        # The import should fail because missing packaging-branch
        srpm = os.path.join(DATA_DIR, "gbp-test-1.1-1.src.rpm")
        assert mock_import(["--packaging-branch=foo", srpm]) == 1
        self._check_log(-1, "Also check the --create-missing-branches")

    def test_filter(self):
        """Test filter option"""
        srpm = os.path.join(DATA_DIR, "gbp-test-1.0-1.src.rpm")
        assert mock_import(["--no-pristine-tar", "--filter=README", "--filter=mydir", srpm]) == 0
        # Check repository state
        repo = GitRepository('gbp-test')
        files = set(['Makefile', 'dummy.sh', 'bar.tar.gz', 'foo.txt',
                     'gbp-test.spec', 'my.patch', 'my2.patch', 'my3.patch'])
        self._check_repo_state(repo, 'master', ['master', 'upstream'], files)

    def test_tagging(self):
        """Test tag options of import-srpm"""
        srpm = os.path.join(DATA_DIR, 'gbp-test-1.0-1.src.rpm')

        # Invalid packaging tag keywords
        assert mock_import(["--no-pristine-tar", "--packaging-tag=%(foo)s", srpm]) == 1
        self._check_log(-1, ".*Missing value 'foo' in *.*")
        # Remove upstream tag
        repo = GitRepository('gbp-test')
        repo.delete_tag('upstream/1.0')

        # Invalid upstream tag keywords
        assert mock_import(["--no-pristine-tar", "--upstream-tag=%(foo)s", srpm]) == 1
        self._check_log(-1, ".*Missing value 'foo' in.*")

        # Try with good keywords, with --skip-packaging-tag
        assert (
            mock_import(
                [
                    "--no-pristine-tar",
                    "--vendor=foo",
                    "--skip-packaging-tag",
                    "--packaging-tag=%(vendor)s/%(version)s",
                    "--upstream-tag=upst/%(version)s",
                    srpm,
                ]
            ) == 0
        )
        assert repo.describe("upstream") == "upst/1.0"
        assert len(repo.get_tags()) == 1

        # Re-import, creating packaging tag
        assert (
            mock_import(
                [
                    "--no-pristine-tar",
                    "--vendor=foo",
                    "--packaging-tag=%(vendor)s/%(version)s",
                    "--upstream-tag=upst/%(version)s",
                    srpm,
                ]
            ) == 0
        )
        assert repo.describe("HEAD") == "foo/1.0-1"
        assert len(repo.get_tags()) == 2

    def test_tagging_native(self):
        """Test tagging of native packages with import-srpm"""
        srpm = os.path.join(DATA_DIR, 'gbp-test-native-1.0-1.src.rpm')

        # Invalid packaging tag keywords
        assert mock_import(["--no-pristine-tar", "--packaging-tag=%(foo)s", srpm, "--native"]) == 1
        self._check_log(-1, ".*Missing value 'foo' in {.*")

        # Try with good keywords, with --skip-packaging-tag.
        # Upstream tag format should not matter
        assert (
            mock_import(
                [
                    "--no-pristine-tar",
                    "--vendor=foo",
                    "--native",
                    "--skip-packaging-tag",
                    "--packaging-tag=%(vendor)s/%(version)s",
                    "--upstream-tag=%(foo)s",
                    srpm,
                ]
            ) == 0
        )
        repo = GitRepository("gbp-test-native")
        assert len(repo.get_tags()) == 0

        # Run again, now creating packaging tag
        assert (
            mock_import(
                [
                    "--no-pristine-tar",
                    "--vendor=foo",
                    "--native",
                    "--packaging-tag=%(vendor)s/%(version)s",
                    "--upstream-tag=%(foo)s",
                    srpm,
                ]
            ) == 0
        )
        assert repo.describe("HEAD") == "foo/1.0-1"

    def test_misc_options(self):
        """Test various options of git-import-srpm"""
        srpm = os.path.join(DATA_DIR, 'gbp-test2-2.0-0.src.rpm')

        assert (
            mock_import(
                [
                    "--no-pristine-tar",
                    "--packaging-branch=pack",
                    "--upstream-branch=orig",
                    "--packaging-dir=packaging",
                    "--packaging-tag=ver_%(upstreamversion)s-rel_%(release)s",
                    "--upstream-tag=orig/%(upstreamversion)s",
                    "--author-is-committer",
                    srpm,
                ]
            ) == 0
        )
        # Check repository state
        repo = GitRepository('gbp-test2')
        files = {'Makefile', 'README', 'dummy.sh', 'packaging/bar.tar.gz',
                 'packaging/foo.txt', 'packaging/gbp-test2.spec',
                 'packaging/gbp-test2-alt.spec', 'packaging/my.patch',
                 'packaging/my2.patch', 'packaging/my3.patch'}
        self._check_repo_state(repo, 'pack', ['pack', 'orig'], files)
        assert len(repo.get_commits()) == 2
        # Check packaging dir
        assert len(repo.get_commits(paths="packaging")) == 1
        # Check tags
        tags = repo.get_tags()
        assert set(tags) == set(["orig/2.0", "ver_2.0-rel_0"])
        # Check git committer/author
        info = repo.get_commit_info("pack")
        assert info["author"].name == "Markus Lehtonen"
        assert info["author"].email == "markus.lehtonen@linux.intel.com"
        assert info["author"].name == info["committer"].name
        assert info["author"].email == info["committer"].email

        # Create a new commit by committing an empty tree
        commit = repo.commit_tree('4b825dc642cb6eb9a060e54bf8d69288fbee4904',
                                  msg="Empty commit", parents=[])
        repo.create_tag('foo/1.0', msg="New tag", commit=commit)
        # Just blindly import another package on top of this to test more options
        os.chdir("gbp-test2")
        srpm = os.path.join(DATA_DIR, "gbp-test-1.0-1.src.rpm")
        assert (
            mock_import(
                [
                    "--upstream-vcs-tag=foo/%(version)s",
                    "--upstream-branch=orig",
                    "--packaging-branch=pack",
                    srpm,
                ]
            ) == 0
        )
        parents = repo.get_commits(until="orig", num=1, options="--format=%P")[0].split()
        assert len(parents) == 2
        assert commit in parents
        assert repo.rev_parse("orig/2.0^{}") in parents


class TestImportUnPacked(ComponentTestBase):
    """Test importing of unpacked source rpms"""

    def setUp(self):
        super(TestImportUnPacked, self).setUp()
        # Unpack some source rpms
        os.mkdir('multi-unpack')
        for pkg in ['gbp-test-1.0-1.src.rpm', 'gbp-test2-2.0-0.src.rpm']:
            unpack_dir = pkg.replace('.src.rpm', '-unpack')
            os.mkdir(unpack_dir)
            pkg_path = os.path.join(DATA_DIR, pkg)
            SrcRpmFile(pkg_path).unpack(unpack_dir)
            SrcRpmFile(pkg_path).unpack('multi-unpack')

    def test_import_dir(self):
        """Test importing of directories"""
        assert mock_import(["--no-pristine-tar", "gbp-test-1.0-1-unpack"]) == 0
        # Check repository state
        repo = GitRepository('gbp-test')
        self._check_repo_state(repo, 'master', ['master', 'upstream'])

        # Check that importing dir with multiple spec files fails
        assert mock_import(["multi-unpack"]) == 1
        self._check_log(-1, "gbp:error: Failed determine spec file: " "Multiple spec files found")

    def test_import_spec(self):
        """Test importing of spec file"""
        specfile = 'gbp-test2-2.0-0-unpack/gbp-test2.spec'
        assert mock_import([specfile]) == 0
        # Check repository state
        assert GitRepository("gbp-test2").is_clean()

    def test_missing_files(self):
        """Test importing of directory with missing packaging files"""
        specfile = 'gbp-test2-2.0-0-unpack/gbp-test2.spec'
        os.unlink('gbp-test2-2.0-0-unpack/my.patch')
        assert mock_import([specfile]) == 1
        self._check_log(-1, "gbp:error: File 'my.patch' listed in spec "
                            "not found")


class TestDownloadImport(ComponentTestBase):
    """Test download functionality"""

    def test_urldownload(self):
        """Test downloading and importing src.rpm from remote url"""
        srpm = 'http://raw.github.com/marquiz/git-buildpackage-rpm-testdata/'\
               'master/gbp-test-1.0-1.src.rpm'
        # Mock to use local files instead of really downloading
        local_fn = os.path.join(DATA_DIR, os.path.basename(srpm))
        import_srpm.urlopen = Mock()
        import_srpm.urlopen.return_value = open(local_fn, 'rb')

        assert mock_import(["--no-pristine-tar", srpm]) == 0
        # Check repository state
        repo = GitRepository('gbp-test')
        self._check_repo_state(repo, 'master', ['master', 'upstream'])

    def test_nonexistent_url(self):
        """Test graceful failure when trying download from non-existent url"""
        srpm = 'http://honk.sigxcpu.org/does/not/exist'
        # Do not connect to remote, mock failure
        import_srpm.urlopen = Mock()
        import_srpm.urlopen.side_effect = urllib.error.HTTPError(srpm, 404, "Not found",
                                                                 None, None)

        assert mock_import([srpm]) == 1
        self._check_log(-1, "gbp:error: Download failed: HTTP Error 404")
        self._clear_log()

    def test_invalid_url(self):
        """Test graceful failure when trying download from invalid url"""
        srpm = 'foob://url.does.not.exist.com/foo.src.rpm'
        assert mock_import([srpm]) == 1
        self._check_log(-1, ".*No such file or directory: 'foob://url.does.not.exist.com/foo.src.rpm")
        self._clear_log()


class TestPristineTar(ComponentTestBase):
    """Test importing with pristine-tar"""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists('/usr/bin/pristine-tar'):
            pytest.skip('Skipping %s:%s as pristine-tar tool is not '
                        'available' % (__name__, cls.__name__))
        super(TestPristineTar, cls).setUpClass()

    def test_basic_import_pristine_tar(self):
        """Test importing of non-native src.rpm, with pristine-tar"""
        srpm = os.path.join(DATA_DIR, "gbp-test-1.0-1.src.rpm")
        assert mock_import(["--pristine-tar", srpm]) == 0
        # Check repository state
        repo = GitRepository('gbp-test')
        self._check_repo_state(repo, 'master', ['master', 'upstream',
                               'pristine-tar'])
        # Two commits: upstream and packaging files
        assert len(repo.get_commits()) == 2

    def test_unsupported_archive(self):
        """Test importing of src.rpm with a zip source archive"""
        srpm = os.path.join(DATA_DIR, "gbp-test-native-1.0-1.src.rpm")
        assert mock_import(["--pristine-tar", srpm]) == 0
        # Check repository state
        repo = GitRepository('gbp-test-native')
        self._check_repo_state(repo, 'master', ['master', 'upstream'])
        # Check that a warning is printed
        self._check_log(-1, "gbp:warning: Ignoring pristine-tar")


class TestBareRepo(ComponentTestBase):
    """Test importing to a bare repository"""

    def test_basic_import_to_bare_repo(self):
        """Test importing of srpm to a bare git repository"""
        srpm = os.path.join(DATA_DIR, 'gbp-test-1.0-1.src.rpm')
        # Create new repo
        repo = GitRepository.create('myrepo', bare=True)
        os.chdir('myrepo')
        assert mock_import([srpm]) == 0
        self._check_repo_state(repo, 'master', ['master', 'upstream'])
        # Patch import to bare repos not supported -> only 2 commits
        assert len(repo.get_commits(until="master")) == 2


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
