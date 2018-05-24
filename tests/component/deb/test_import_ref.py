# vim: set fileencoding=utf-8 :
#
# (C) 2015,2017 Guido Günther <agx@sigxcpu.org>
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

from gbp.scripts.import_ref import main as import_ref

from nose.tools import ok_, eq_


def _dsc_file(pkg, version, dir='dsc-3.0'):
    return os.path.join(DEB_TEST_DATA_DIR, dir, '%s_%s.dsc' % (pkg, version))


DEFAULT_DSC = _dsc_file('hello-debhelper', '2.6-2')


class TestImportRef(ComponentTestBase):
    """Test importing of new upstream versions"""
    pkg = "hello-debhelper"
    def_branches = ['master', 'upstream', 'pristine-tar']

    def _orig(self, version, dir='dsc-3.0'):
        return os.path.join(DEB_TEST_DATA_DIR,
                            dir,
                            '%s_%s.orig.tar.gz' % (self.pkg, version))

    @RepoFixtures.quilt30(DEFAULT_DSC, opts=['--pristine-tar'])
    def test_from_branch(self, repo):
        """
        Test that importing a upstream git from a branch works
        """
        eq_(len(repo.get_commits()), 2)
        ok_(import_ref(['arg0',
                        '--upstream-tree=BRANCH',
                        '--upstream-tag=theupstream/%(version)s',
                        '-uaversion']) == 0)
        self._check_repo_state(repo, 'master', self.def_branches,
                               tags=['debian/2.6-2', 'theupstream/aversion', 'upstream/2.6'])
        eq_(len(repo.get_commits()), 3)

    @RepoFixtures.quilt30(DEFAULT_DSC, opts=['--pristine-tar'])
    def test_from_version(self, repo):
        """
        Test that importing a upstream git from a given version works
        """
        eq_(len(repo.get_commits()), 2)
        ok_(import_ref(['arg0',
                        '--upstream-tree=VERSION',
                        '--upstream-tag=upstream/%(version)s',
                        '-u2.6']) == 0)
        self._check_repo_state(repo, 'master', self.def_branches,
                               tags=['debian/2.6-2', 'upstream/2.6'])
        eq_(len(repo.get_commits()), 3)

    @RepoFixtures.quilt30(DEFAULT_DSC, opts=['--pristine-tar'])
    def test_from_committish(self, repo):
        """
        Test that importing a upstream git from another commit works
        """
        eq_(len(repo.get_commits()), 2)
        ok_(import_ref(['arg0',
                        '--upstream-tree=upstream',
                        '--upstream-tag=upstream/%(version)s',
                        '-u2.6']) == 0)
        self._check_repo_state(repo, 'master', self.def_branches,
                               tags=['debian/2.6-2', 'upstream/2.6'])
        eq_(len(repo.get_commits()), 3)
