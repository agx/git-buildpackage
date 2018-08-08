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
    """Test pulling from a remote"""

    @RepoFixtures.native()
    def test_pull_explicit_remote(self, repo):
        """Test that pulling of debian native packages works (explicit remote)"""
        dest = os.path.join(self._tmpdir, 'cloned_repo')
        clone(['arg0', repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])
        eq_(pull(['argv0', 'origin']), 0)
        assert len(repo.get_commits()) == 1

    @RepoFixtures.native()
    def test_pull_default_remote(self, repo):
        """Test that pulling of debian native packages works (default remote)"""
        dest = os.path.join(self._tmpdir, 'cloned_repo')
        clone(['arg0', repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])
        eq_(pull(['argv0']), 0)
        assert len(repo.get_commits()) == 1

    @RepoFixtures.quilt30()
    def test_pull_all(self, repo):
        """Test the '--all' commandline option"""
        # Create new branch in repo
        repo.create_branch('foob')

        # Clone and create new commits in origin
        dest = os.path.join(self._tmpdir, 'cloned_repo')
        clone(['arg0', '--all', repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        tmp_workdir = os.path.join(self._tmpdir, 'tmp_workdir')
        os.mkdir(tmp_workdir)
        with open(os.path.join(tmp_workdir, 'new_file'), 'w'):
            pass
        repo.commit_dir(tmp_workdir, 'New commit in master', branch='master')
        repo.commit_dir(tmp_workdir, 'New commit in foob', branch='foob')

        # Check that the branch is not updated when --all is not used
        eq_(pull(['argv0']), 0)
        eq_(len(cloned.get_commits(until='master')), 3)
        eq_(len(cloned.get_commits(until='upstream')), 1)
        eq_(len(cloned.get_commits(until='foob')), 2)

        # Check that --all updates all branches
        repo.commit_dir(tmp_workdir, 'New commit in upstream', branch='upstream')
        eq_(pull(['argv0', '--all']), 0)
        eq_(len(cloned.get_commits(until='foob')), 3)
        eq_(len(cloned.get_commits(until='upstream')), 2)

    @RepoFixtures.native()
    def test_tracking(self, repo):
        """Test that --track-missing picks up missing branches"""
        dest = os.path.join(self._tmpdir, 'cloned_repo')
        clone(['arg0', repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        os.chdir(cloned.path)
        self._check_repo_state(cloned, 'master', ['master'])
        # Pull initially
        eq_(pull(['argv0']), 0)
        assert len(repo.get_commits()) == 1
        self._check_repo_state(cloned, 'master', ['master'])

        # Pick up missing branches (none exist yet)
        eq_(pull(['argv0', '--track-missing']), 0)
        assert len(repo.get_commits()) == 1
        self._check_repo_state(cloned, 'master', ['master'])

        # Pick up missing branches
        repo.create_branch('pristine-tar')
        repo.create_branch('upstream')
        eq_(pull(['argv0', '--track-missing', '--pristine-tar']), 0)
        assert len(repo.get_commits()) == 1
        self._check_repo_state(cloned, 'master', ['master', 'pristine-tar', 'upstream'])
