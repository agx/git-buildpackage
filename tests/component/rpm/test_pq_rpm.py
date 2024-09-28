# vim: set fileencoding=utf-8 :
#
# (C) 2013 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""Tests for the gbp pq-rpm tool"""

import os
import tempfile

import pytest

from gbp.scripts.pq_rpm import main as pq
from gbp.git import GitRepository
from gbp.command_wrappers import GitCommand
from gbp.rpm import SpecFile

from tests.component.rpm import RpmRepoTestBase
from tests.testutils import capture_stderr

# Disable "Method could be a function warning"
# pylint: disable=R0201


def mock_pq(args):
    """Wrapper for pq"""
    # Call pq-rpm with added arg0
    return pq(['arg0'] + args)


class TestPqRpm(RpmRepoTestBase):
    """Basic tests for gbp-pq-rpm"""

    def _has_patches(self, specfile, patches):
        spec = SpecFile(specfile)
        assert sorted([p["linevalue"] for p in spec._patches().values()]) == sorted(patches)

    def test_invalid_args(self):
        """See that pq-rpm fails gracefully when called with invalid args"""
        GitRepository.create('.')
        # Test empty args
        assert mock_pq([]) == 1
        self._check_log(0, 'gbp:error: No action given.')
        self._clear_log()

        # Test invalid command
        assert mock_pq(["mycommand"]) == 1
        self._check_log(0, "gbp:error: Unknown action 'mycommand'")
        self._clear_log()

        # Test invalid cmdline options
        with pytest.raises(SystemExit):
            with capture_stderr():
                mock_pq(['--invalid-arg=123'])

    def test_import_outside_repo(self):
        """Run pq-rpm when not in a git repository"""
        assert mock_pq(["export"]) == 1
        self._check_log(0, "gbp:error: %s is not a git repository" % os.path.abspath(os.getcwd()))

    def test_import_export(self):
        """Basic test for patch import and export"""
        repo = self.init_test_repo('gbp-test')
        branches = repo.get_local_branches() + ['patch-queue/master']
        # Test import
        assert mock_pq(["import"]) == 0
        files = ["AUTHORS", "dummy.sh", "Makefile", "NEWS", "README", "mydir/myfile.txt"]
        patches = ["my.patch", "0001-my-gz.patch", "0002-my-bzip2.patch", "0003-my2.patch"]

        branches.append("patch-queue/master")
        self._check_repo_state(repo, "patch-queue/master", branches, files)
        assert repo.get_merge_base("upstream", "patch-queue/master") == repo.rev_parse("upstream")
        assert len(repo.get_commits("", "upstream")) < len(
            repo.get_commits("", "patch-queue/master")
        )

        # Test export
        assert mock_pq(["export", "--upstream-tag", "upstream/%(version)s"]) == 0
        files = [".gbp.conf", ".gitignore", "bar.tar.gz", "foo.txt", "gbp-test.spec"] + patches
        self._check_repo_state(repo, "master", branches, files, clean=False)
        assert repo.status()[" M"] == [b"gbp-test.spec"]
        self._has_patches("gbp-test.spec", patches)

        # Another export after removing some patches
        os.unlink("0001-my-gz.patch")
        assert mock_pq(["export"]) == 0
        self._check_repo_state(repo, "master", branches, files, clean=False)
        self._has_patches("gbp-test.spec", patches)

    def test_import_export2(self):
        """Another test for import and export"""
        repo = self.init_test_repo('gbp-test2')
        branches = repo.get_local_branches() + ['patch-queue/master-orphan']
        repo.set_branch('master-orphan')
        # Import
        assert mock_pq(["import"]) == 0
        files = ["dummy.sh", "Makefile", "README", "mydir/myfile.txt"]
        patches = ["packaging/0001-PATCH-My-modification.patch", "my.patch"]
        self._check_repo_state(repo, "patch-queue/master-orphan", branches, files)

        # Test export with --drop
        branches.remove("patch-queue/master-orphan")
        assert (
            mock_pq(
                [
                    "export",
                    "--drop",
                    "--upstream-tag",
                    "upstream/%(version)s",
                    "--spec-file",
                    "packaging/gbp-test2.spec",
                ]
            ) == 0
        )
        self._check_repo_state(repo, "master-orphan", branches, clean=False)
        assert repo.status()[" M"] == [b"packaging/gbp-test2.spec"]
        self._has_patches("packaging/gbp-test2.spec", patches)

    def test_rebase(self):
        """Basic test for rebase action"""
        repo = self.init_test_repo('gbp-test')
        repo.rename_branch('pq/master', 'patch-queue/master')
        repo.set_branch('patch-queue/master')
        branches = repo.get_local_branches()
        # Make development branch out-of-sync
        GitCommand("rebase")(['--onto', 'upstream^', 'upstream'])
        # Sanity check for our git rebase...
        assert repo.get_merge_base("patch-queue/master", "upstream") != repo.rev_parse("upstream")

        # Do rebase
        assert mock_pq(["rebase"]) == 0
        self._check_repo_state(repo, "patch-queue/master", branches)
        assert repo.get_merge_base("patch-queue/master", "upstream") == repo.rev_parse("upstream")

        # Get to out-of-sync, again, and try rebase from master branch
        GitCommand("rebase")(["--onto", "upstream^", "upstream"])
        assert mock_pq(["switch"]) == 0
        assert mock_pq(["rebase"]) == 0
        self._check_repo_state(repo, "patch-queue/master", branches)
        assert repo.get_merge_base("patch-queue/master", "upstream") == repo.rev_parse("upstream")

    def test_switch(self):
        """Basic test for switch action"""
        repo = self.init_test_repo('gbp-test')
        branches = repo.get_local_branches() + ['patch-queue/master']
        repo.create_branch('patch-queue/master')

        # Switch to base branch and back to pq
        assert mock_pq(["switch"]) == 0
        self._check_repo_state(repo, "patch-queue/master", branches)
        assert mock_pq(["switch"]) == 0
        self._check_repo_state(repo, "master", branches)

    def test_switch_drop(self):
        """Basic test for drop action"""
        repo = self.init_test_repo('gbp-test')
        repo.rename_branch('pq/master', 'patch-queue/master')
        repo.set_branch('patch-queue/master')
        branches = repo.get_local_branches()

        # Switch to master
        assert mock_pq(["switch"]) == 0
        self._check_repo_state(repo, "master", branches)

        # Drop should succeed when on master branch
        assert mock_pq(["drop"]) == 0
        branches.remove("patch-queue/master")
        self._check_repo_state(repo, "master", branches)

    def test_drop_pq(self):
        """drop action should work on pq branch"""
        repo = self.init_test_repo('gbp-test')
        repo.rename_branch('pq/master', 'patch-queue/master')
        repo.set_branch('patch-queue/master')
        branches = repo.get_local_branches()

        # Switch to master
        assert mock_pq(["switch"]) == 0
        self._check_repo_state(repo, "master", branches)

        # Drop should succeed when on master branch
        assert mock_pq(["drop"]) == 0
        branches.remove("patch-queue/master")
        self._check_repo_state(repo, "master", branches)

    def test_force_import(self):
        """Test force import"""
        repo = self.init_test_repo('gbp-test')
        pkg_files = [f.decode() for f in repo.list_files()]
        repo.rename_branch('pq/master', 'patch-queue/master')
        repo.set_branch('patch-queue/master')
        branches = repo.get_local_branches()
        pq_files = [f.decode() for f in repo.list_files()]

        # Re-import should fail
        assert mock_pq(["import"]) == 1
        self._check_log(0, "gbp:error: Already on a patch-queue branch")
        self._check_repo_state(repo, 'patch-queue/master', branches, pq_files)

        # Mangle pq branch and try force import on top of that
        repo.force_head("master", hard=True)
        self._check_repo_state(repo, "patch-queue/master", branches, pkg_files)
        assert mock_pq(["import", "--force"]) == 0
        # .gbp.conf won't get imported by pq
        pq_files.remove('.gbp.conf')
        self._check_repo_state(repo, 'patch-queue/master', branches, pq_files)

        # Switch back to master
        assert mock_pq(["switch"]) == 0
        self._check_repo_state(repo, "master", branches, pkg_files)

        # Import should fail
        assert mock_pq(["import"]) == 1
        self._check_log(-1, "gbp:error: Patch-queue branch .* already exists")
        self._check_repo_state(repo, 'master', branches, pkg_files)

        # Force import should succeed
        assert mock_pq(["import", "--force"]) == 0
        self._check_repo_state(repo, "patch-queue/master", branches, pq_files)

    def test_apply(self):
        """Basic test for apply action"""
        repo = self.init_test_repo('gbp-test')
        upstr_files = ['dummy.sh', 'Makefile', 'README']
        branches = repo.get_local_branches() + ['patch-queue/master']

        # No patch given
        assert mock_pq(["apply"]) == 1
        self._check_log(-1, "gbp:error: No patch name given.")

        # Create a pristine pq-branch
        repo.create_branch('patch-queue/master', 'upstream')

        # Apply patch
        with tempfile.NamedTemporaryFile() as tmp_patch:
            tmp_patch.write(repo.show('master:%s' % 'my.patch'))
            tmp_patch.file.flush()
            assert mock_pq(["apply", tmp_patch.name]) == 0
            self._check_repo_state(repo, "patch-queue/master", branches, upstr_files)

        # Apply another patch, now when already on pq branch
        with tempfile.NamedTemporaryFile() as tmp_patch:
            tmp_patch.write(repo.show('master:%s' % 'my2.patch'))
            tmp_patch.file.flush()
            assert mock_pq(["apply", tmp_patch.name]) == 0
        self._check_repo_state(
            repo, "patch-queue/master", branches, upstr_files + ["mydir/myfile.txt"]
        )

    def test_option_patch_numbers(self):
        """Test the --patch-numbers cmdline option"""
        repo = self.init_test_repo('gbp-test')
        repo.rename_branch('pq/master', 'patch-queue/master')
        branches = repo.get_local_branches()
        # Export
        assert mock_pq(["export", "--no-patch-numbers"]) == 0
        patches = ["my-gz.patch", "my-bzip2.patch", "my2.patch", "my.patch"]
        files = [".gbp.conf", ".gitignore", "bar.tar.gz", "foo.txt", "gbp-test.spec"] + patches
        self._check_repo_state(repo, "master", branches, files, clean=False)
        self._has_patches("gbp-test.spec", patches)

    def test_option_tmp_dir(self):
        """Test the --tmp-dir cmdline option"""
        self.init_test_repo("gbp-test")
        assert mock_pq(["import", "--tmp-dir=foo/bar"]) == 0
        # Check that the tmp dir basedir was created
        assert os.path.isdir("foo/bar")

    def test_option_upstream_tag(self):
        """Test the --upstream-tag cmdline option"""
        repo = self.init_test_repo('gbp-test')

        # Non-existent upstream-tag -> failure
        assert mock_pq(["import", "--upstream-tag=foobar/%(upstreamversion)s"]) == 1
        self._check_log(-1, "gbp:error: Couldn't find upstream version")

        # Create tag -> import should succeed
        repo.create_tag("foobar/1.1", msg="test tag", commit="upstream")
        assert mock_pq(["import", "--upstream-tag=foobar/%(upstreamversion)s"]) == 0

    def test_option_spec_file(self):
        """Test --spec-file commandline option"""
        self.init_test_repo('gbp-test')

        # Non-existent spec file should lead to failure
        assert mock_pq(["import", "--spec-file=foo.spec"]) == 1
        self._check_log(-1, "gbp:error: Can't parse spec: Unable to read spec")
        # Correct spec file
        assert mock_pq(["import", "--spec-file=gbp-test.spec"]) == 0

        # Force import on top to test parsing spec from another branch
        assert (
            mock_pq(
                [
                    "import",
                    "--spec-file=gbp-test.spec",
                    "--force",
                    "--upstream-tag",
                    "upstream/%(version)s",
                ]
            ) == 0
        )

        # Test with export, too
        assert mock_pq(["export", "--spec-file=foo.spec"]) == 1
        self._check_log(-1, "gbp:error: Can't parse spec: Unable to read spec")
        assert mock_pq(["export", "--spec-file=gbp-test.spec"]) == 0

    def test_option_packaging_dir(self):
        """Test --packaging-dir command line option"""
        self.init_test_repo('gbp-test')

        # Wrong packaging dir should lead to failure
        assert mock_pq(["import", "--packaging-dir=foo"]) == 1
        self._check_log(-1, "gbp:error: Can't parse spec: No spec file found")
        # Use correct packaging dir
        assert mock_pq(["import", "--packaging-dir=."]) == 0

        # Test with export, --spec-file option should override packaging dir
        assert (
            mock_pq(
                [
                    "export",
                    "--packaging-dir=foo",
                    "--upstream-tag",
                    "upstream/%(version)s",
                    "--spec-file=gbp-test.spec",
                ]
            ) == 0
        )

    def test_export_with_merges(self):
        """Test exporting pq-branch with merge commits"""
        repo = self.init_test_repo('gbp-test')
        repo.rename_branch('pq/master', 'patch-queue/master')
        repo.set_branch('patch-queue/master')
        branches = repo.get_local_branches()

        # Create a merge commit in pq-branch
        patches = repo.format_patches("HEAD^", "HEAD", ".")
        repo.force_head("HEAD^", hard=True)
        repo.commit_dir(".", "Merge with master", "patch-queue/master", ["master"])
        merge_rev = repo.rev_parse("HEAD", short=7)
        assert mock_pq(["apply", patches[0].decode()]) == 0
        upstr_rev = repo.rev_parse("upstream", short=7)
        os.unlink(patches[0])

        # Export should create diff up to the merge point and one "normal" patch
        assert mock_pq(["export"]) == 0
        patches = ["my.patch", "%s-to-%s.diff" % (upstr_rev, merge_rev), "0002-my2.patch"]
        files = [".gbp.conf", ".gitignore", "bar.tar.gz", "foo.txt", "gbp-test.spec"] + patches
        self._check_repo_state(repo, "master", branches, files, clean=False)
        self._has_patches("gbp-test.spec", patches)

    def test_import_unapplicable_patch(self):
        """Test import when a patch does not apply"""
        repo = self.init_test_repo('gbp-test')
        branches = repo.get_local_branches()
        # Mangle patch
        with open("my2.patch", "w") as patch_file:
            patch_file.write("-this-does\n+not-apply\n")
        assert mock_pq(["import"]) == 1
        self._check_log(-2, "Please commit your changes or stash them")
        self._check_repo_state(repo, 'master', branches, clean=False)

        # Now commit the changes to the patch and try again
        repo.add_files(["my2.patch"], force=True)
        repo.commit_files(["my2.patch"], msg="Mangle patch")
        assert mock_pq(["import"]) == 1
        self._check_log(-1, "gbp:error: Import failed: Error running git apply")
        self._check_repo_state(repo, 'master', branches, clean=False)
