# vim: set fileencoding=utf-8 :
#
# (C) 2017 Guido Günther <agx@sigxcpu.org>
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
                             ComponentTestGitRepository)
from tests.component.deb.fixtures import RepoFixtures

from nose.tools import eq_

from gbp.scripts.clone import main as clone
from gbp.scripts.pull import main as pull


class TestPull(ComponentTestBase):
    """Test cloning from a remote"""

    @RepoFixtures.native()
    def test_pull_explicit_remote(self, repo):
        """Test that pulling of debian native packages works"""
        dest = os.path.join(self._tmpdir, 'cloned_repo')
        clone(['arg0', repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])
        eq_(pull(['argv0', 'origin']), 0)
        assert len(repo.get_commits()) == 1

    @RepoFixtures.native()
    def test_pull_default_remote(self, repo):
        """Test that pulling of debian native packages works"""
        dest = os.path.join(self._tmpdir, 'cloned_repo')
        clone(['arg0', repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])
        eq_(pull(['argv0']), 0)
        assert len(repo.get_commits()) == 1
