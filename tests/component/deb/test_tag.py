# vim: set fileencoding=utf-8 :
#
# (C) 2015-2017 Guido Günther <agx@sigxcpu.org>
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

from tests.component import ComponentTestBase
from tests.component.deb import DEB_TEST_DATA_DIR
from tests.component.deb.fixtures import RepoFixtures

from nose.tools import ok_, eq_

from gbp.scripts.tag import main as tag
from gbp.scripts.pq import main as pq


class TestTag(ComponentTestBase):
    """Test tagging a debian package"""

    @staticmethod
    def _dsc_name(pkg, version, dir):
        return os.path.join(DEB_TEST_DATA_DIR,
                            dir,
                            '%s_%s.dsc' % (pkg, version))

    @RepoFixtures.native()
    def test_tag(self, repo):
        """Test that tagging a native debian package works"""
        repo.delete_tag('debian/0.4.14')  # make sure we can tag again
        eq_(repo.has_tag('debian/0.4.14'), False)
        ret = tag(['arg0',
                   '--posttag=printenv > posttag.out'])
        ok_(ret == 0, "Tagging the package failed")
        eq_(os.path.exists('posttag.out'), True)
        self.check_hook_vars('posttag', [("GBP_TAG", "debian/0.4.14"),
                                         ("GBP_BRANCH", "master"),
                                         "GBP_SHA1"])
        eq_(repo.head, repo.rev_parse('debian/0.4.14^{}'))

    @RepoFixtures.quilt30()
    def test_tag_pq_branch(self, repo):
        ret = pq(['argv0', 'import'])
        eq_(repo.rev_parse('master'), repo.rev_parse('debian/2.8-1^{}'))
        eq_(ret, 0)
        eq_(repo.branch, 'patch-queue/master')
        self.add_file(repo, 'foo.txt')
        ret = tag(['argv0', '--retag', '--ignore-branch'])
        eq_(ret, 0)
        eq_(repo.branch, 'patch-queue/master')
        eq_(repo.rev_parse('patch-queue/master^{}^'), repo.rev_parse('debian/2.8-1^{}'))

    @RepoFixtures.quilt30()
    def test_tag_detached_head(self, repo):
        """
        Test that tagging works with an detached head (#863167)
        """
        eq_(repo.rev_parse('master^{}'), repo.rev_parse('debian/2.8-1^{}'))
        self.add_file(repo, 'debian/foo.txt')
        repo.checkout("HEAD~")
        ret = tag(['argv0', '--retag', '--ignore-branch'])
        eq_(ret, 0)
        repo.checkout("master")
        eq_(repo.rev_parse('master~^{}'), repo.rev_parse('debian/2.8-1^{}'))
