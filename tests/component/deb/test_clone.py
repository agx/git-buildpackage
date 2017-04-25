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

from nose.tools import ok_

from gbp.scripts.clone import main as clone


class TestClone(ComponentTestBase):
    """Test cloning from a remote"""

    @RepoFixtures.native()
    def test_clone_nonempty(self, repo):
        """Test that cloning into an existing dir fails"""
        os.chdir('..')
        ok_(clone(['arg0', repo.path]) == 1,
            "Cloning did no fail as expected")
        self._check_log(-2,
                        "gbp:error: Git command failed: Error "
                        "running git clone: fatal: destination path "
                        "'git-buildpackage' already exists and is not "
                        "an empty directory.")

    @RepoFixtures.native()
    def test_clone_native(self, repo):
        """Test that cloning of debian native packages works"""
        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        clone(['arg0',
               '--postclone=printenv > postclone.out',
               repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])
        assert len(cloned.get_commits()) == 1
        self.check_hook_vars('postclone', ["GBP_GIT_DIR"])

    @skipUnless(os.getenv("GBP_NETWORK_TESTS"), "network tests disabled")
    def test_clone_vcsgit_ok(self):
        """Test that cloning from vcs-git urls works"""
        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        ret = clone(['arg0', "vcsgit:libvirt-glib", dest])
        self.assertEquals(ret, 0)
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'debian/sid', ['debian/sid', 'upstream/latest'])

    @skipUnless(os.getenv("GBP_NETWORK_TESTS"), "network tests disabled")
    def test_clone_vcsgit_fail(self):
        """Test that cloning from vcs-git urls fails as expected"""
        ret = clone(['arg0', "vcsgit:doesnotexist"])
        self.assertEquals(ret, 1)
        self._check_log(-1, "gbp:error: Can't find a source package for 'doesnotexist'")

    @skipUnless(os.getenv("GBP_NETWORK_TESTS"), "network tests disabled")
    def test_clone_github(self):
        """Test that cloning from github urls works"""
        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        ret = clone(['arg0', "github:agx/git-buildpackage", dest])
        self.assertEquals(ret, 0)
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])
