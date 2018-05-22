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
import subprocess

from tests.component import ComponentTestBase

from tests.component.deb.fixtures import RepoFixtures
from tests.testutils import skip_without_cmd

from gbp.git import GitRepository
from gbp.scripts.push import main as push


class TestPush(ComponentTestBase):
    """Test pushing to remote repos"""

    def setUp(self):
        ComponentTestBase.setUp(self)
        self.target = GitRepository.create('target', bare=True)

    @RepoFixtures.native()
    def test_push_native(self, repo):
        repo.add_remote_repo('origin', self.target.path)
        self.assertEquals(push(['argv0']), 0)
        self._check_repo_state(self.target, 'master',
                               ['master'],
                               tags=['debian/0.4.14'])
        self.assertEquals(repo.head, self.target.head)

    @RepoFixtures.quilt30()
    def test_push_upstream(self, repo):
        repo.add_remote_repo('origin', self.target.path)
        self.assertEquals(push(['argv0']), 0)
        self._check_repo_state(self.target, 'master',
                               ['master', 'upstream'],
                               tags=['debian/2.8-1', 'upstream/2.8'])
        self.assertEquals(repo.head, self.target.head)

    @RepoFixtures.quilt30(opts=['--pristine-tar'])
    def test_push_pristine_tar(self, repo):
        repo.add_remote_repo('origin', self.target.path)
        self.assertEquals(push(['argv0', '--pristine-tar']), 0)
        self._check_repo_state(self.target, 'master',
                               ['master', 'upstream', 'pristine-tar'],
                               tags=['debian/2.8-1', 'upstream/2.8'])
        self.assertEquals(repo.head, self.target.head)

    @RepoFixtures.quilt30(opts=['--pristine-tar'])
    def test_push_detached_head(self, repo):
        repo.checkout("HEAD^{commit}")
        repo.add_remote_repo('origin', self.target.path)
        self.assertEquals(push(['argv0', '--ignore-branch']), 0)
        # Since branch head is detached we don't push it but upstream
        # branch and tags must be there:
        self._check_repo_state(self.target, None,
                               ['upstream'],
                               tags=['debian/2.8-1', 'upstream/2.8'])

    @RepoFixtures.quilt30()
    def test_push_skip_upstream(self, repo):
        repo.add_remote_repo('origin', self.target.path)
        self.assertEquals(push(['argv0', '--upstream-branch=']), 0)
        self._check_repo_state(self.target, 'master',
                               ['master'],
                               tags=['debian/2.8-1', 'upstream/2.8'])
        self.assertEquals(repo.head, self.target.head)

    @RepoFixtures.native()
    def test_push_tag_ne_branch(self, repo):
        repo.add_remote_repo('origin', self.target.path)
        self.add_file(repo, "foo.txt", "foo")
        self.assertEquals(push(['argv0']), 0)
        self._check_repo_state(self.target, 'master',
                               ['master'],
                               tags=['debian/0.4.14'])
        self.assertEquals(repo.rev_parse("HEAD^"),
                          self.target.head)

    @RepoFixtures.quilt30()
    def test_not_debian_branch(self, repo):
        repo.add_remote_repo('origin', self.target.path)
        repo.create_branch("foo")
        repo.set_branch("foo")
        self.assertEquals(push(['argv0']), 1)
        self._check_log(-2, ".*You are not on branch 'master' but on 'foo'")

    @skip_without_cmd('debchange')
    @RepoFixtures.quilt30()
    def test_dont_push_unreleased(self, repo):
        repo.add_remote_repo('origin', self.target.path)
        subprocess.check_call(["debchange", "-i", "foo"])
        self.assertEquals(push(['argv0']), 0)
        self._check_repo_state(self.target, None,
                               ['upstream'],
                               tags=['upstream/2.8'])

    @RepoFixtures.quilt30()
    def test_push_not_origin(self, repo):
        repo.add_remote_repo('notorigin', self.target.path)
        self.assertEquals(push(['argv0', 'notorigin']), 0)
        self._check_repo_state(self.target, 'master',
                               ['master', 'upstream'],
                               tags=['debian/2.8-1', 'upstream/2.8'])
        self.assertEquals(repo.head, self.target.head)

    @RepoFixtures.quilt30()
    def test_push_not_origin_detect(self, repo):
        repo.add_remote_repo('notorigin', self.target.path)
        repo.set_config("branch.master.remote", "notorigin")
        repo.set_config("branch.master.merge", "refs/heads/master")
        self.assertEquals(push(['argv0']), 0)
        self._check_repo_state(self.target, 'master',
                               ['master', 'upstream'],
                               tags=['debian/2.8-1', 'upstream/2.8'])
        self.assertEquals(repo.head, self.target.head)

    @RepoFixtures.quilt30()
    def test_push_failure(self, repo):
        """
        Check that in case of failure we push all other branches/tags
        """
        # Create a broken tag so pushing to it fails:
        tag = os.path.join(self.target.path, 'refs', 'tags', 'debian', '2.8-1')
        os.mkdir(os.path.dirname(tag))
        with open(tag, 'w') as f:
            f.write("broken_tag")

        repo.add_remote_repo('origin', self.target.path)
        self.assertEquals(push(['argv0']), 1)
        self._check_repo_state(self.target, 'master',
                               ['master', 'upstream'],
                               tags=['upstream/2.8'])
        self.assertEquals(repo.head, self.target.head)
        self._check_in_log('.*Error running git push: .*refs/tags/debian/2.8-1')
        self._check_log(-1, ".*Failed to push some refs")
