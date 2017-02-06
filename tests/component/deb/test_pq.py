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
        os.chdir(repo.path)
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
