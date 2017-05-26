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

from tests.component import (ComponentTestBase)
from tests.component.deb.fixtures import RepoFixtures

from nose.tools import ok_, eq_

from gbp.scripts.pq import main as pq


class TestPq(ComponentTestBase):
    """Test gbp pq"""

    def _test_pq(self, repo, action, opts=[]):
        args = ['arg0', action] + opts
        os.chdir(os.path.abspath(repo.path))
        ret = pq(args)
        ok_(ret == 0, "Running gbp pq %s failed" % action)

    @RepoFixtures.quilt30()
    def test_empty_cycle(self, repo):
        eq_(repo.has_branch('patch-queue/master'), False)
        self._test_pq(repo, 'import')
        eq_(repo.has_branch('patch-queue/master'), True)
        self._test_pq(repo, 'rebase')
        self._test_pq(repo, 'export')
        eq_(repo.has_branch('patch-queue/master'), True)
        self._test_pq(repo, 'drop')
        eq_(repo.has_branch('patch-queue/master'), False)

    @RepoFixtures.quilt30()
    def test_rename(self, repo):
        patch = os.path.join(repo.path, 'debian/patches/0001-Rename.patch')

        repo.set_config('diff.renames', 'true')
        self._test_pq(repo, 'import')
        repo.rename_file('configure.ac', 'renamed')
        repo.commit_all("Rename")
        self._test_pq(repo, 'export')
        self.assertTrue(
            os.path.exists(patch))
        # Check the file was removed and added, not renamed
        with open(patch) as f:
            self.assertTrue('rename from' not in f.read())
            self.assertTrue('rename to' not in f.read())
