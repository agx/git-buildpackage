# vim: set fileencoding=utf-8 :
#
# (C) 2016 Guido Günther <agx@sigxcpu.org>
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

import os

from tests.component import (ComponentTestBase,
                             ComponentTestGitRepository,
                             skipUnless)
from tests.component.deb.fixtures import RepoFixtures

from gbp.scripts.clone import main as clone


class TestClone(ComponentTestBase):
    """Test cloning from a remote"""

    @RepoFixtures.native()
    def test_clone_nonempty(self, repo):
        """Test that cloning into an existing dir fails"""
        os.chdir("..")
        assert clone(["arg0", repo.path]) == 1, "Cloning did no fail as expected"
        self._check_log(
            -2,
            "gbp:error: Git command failed: Error "
            "running git clone: fatal: destination path "
            "'git-buildpackage' already exists and is not "
            "an empty directory.",
        )

    @RepoFixtures.native()
    def test_clone_native(self, repo):
        """Test that cloning of debian native packages works"""
        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        clone(['arg0',
               '--postclone=printenv > ../postclone.out',
               repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])
        assert len(cloned.get_commits()) == 1
        self.check_hook_vars('../postclone', ["GBP_GIT_DIR"])

    @skipUnless(os.getenv("GBP_NETWORK_TESTS"), "network tests disabled")
    def test_clone_vcsgit_ok(self):
        """Test that cloning from vcs-git urls works"""
        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        self._check_success(clone(['arg0', "--add-upstream-vcs", "vcsgit:libvirt-glib", dest]))
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'debian/sid', ['debian/sid', 'upstream/latest'])
        assert cloned.has_remote_repo("upstreamvcs")
        assert 'upstreamvcs/master' in cloned.get_remote_branches()

    @skipUnless(os.getenv("GBP_NETWORK_TESTS"), "network tests disabled")
    def test_clone_vcsgit_fail(self):
        """Test that cloning from vcs-git urls fails as expected"""
        ret = clone(['arg0', "vcsgit:doesnotexist"])
        self.assertEqual(ret, 1)
        self._check_log(-1, "gbp:error: Can't find any vcs-git URL for 'doesnotexist'")

    @skipUnless(os.getenv("GBP_NETWORK_TESTS"), "network tests disabled")
    def test_clone_github(self):
        """Test that cloning from github urls works"""
        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        self._check_success(clone(['arg0', "github:agx/git-buildpackage", dest]))
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])

    @RepoFixtures.native()
    def test_clone_without_attrs(self, repo):
        """Test that cloning a repo without harmful attrs does nothing"""
        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        self._check_success(clone(['arg0', repo.path, dest]))
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])

        attrs_file = os.path.join(dest, '.git', 'info', 'attributes')
        # file may be empty or absent
        self.assertFalse(os.path.exists(attrs_file) and os.path.getsize(attrs_file),
                         "%s is non-empty" % attrs_file)

    @RepoFixtures.native()
    def test_clone_with_attrs(self, repo):
        """Test that cloning a repo with harmful attrs disarms them and avoids line ending conversion"""
        with open('test.csv', 'wb') as f:
            f.write(b'line1\nline2\n')
        repo.add_files('test.csv')
        repo.commit_files('test.csv', msg="add test.csv")
        with open('.gitattributes', 'w') as f:
            f.write('*.csv text eol=crlf')
        repo.add_files('.gitattributes')
        repo.commit_files('.gitattributes', msg="add .gitattributes")

        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        clone(['arg0',
               repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])

        attrs_file = os.path.join(dest, '.git', 'info', 'attributes')
        assert os.path.exists(attrs_file), "%s is missing" % attrs_file

        with open(attrs_file) as f:
            attrs = sorted(f.read().splitlines())

        expected_gitattrs = [
            '# Added by git-buildpackage to disable .gitattributes found in the upstream tree',
            '* -export-ignore',
            '* -export-subst',
            '* dgit-defuse-attrs',
            '[attr]dgit-defuse-attrs  -text -eol -crlf -ident -filter -working-tree-encoding',
        ]
        self.assertEqual(attrs, expected_gitattrs)

        test_file = os.path.join(dest, 'test.csv')
        with open(test_file, 'rb') as f:
            test_contents = f.read()
        expected_test_contents = b'line1\nline2\n'
        self.assertEqual(test_contents, expected_test_contents)
