# vim: set fileencoding=utf-8 :
#
# (C) 2015 Guido Günther <agx@sigxcpu.org>
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

from gbp.scripts.import_orig import main as import_orig
from gbp.git.repository import GitRepository

from nose.tools import ok_


class TestImportOrig(ComponentTestBase):
    """Test importing of new upstream sources"""

    pkg = "hello-debhelper"
    def_branches = ['master', 'upstream', 'pristine-tar']

    def _orig(self, version):
        return os.path.join(DEB_TEST_DATA_DIR,
                            'dsc-3.0',
                            '%s_%s.orig.tar.gz' % (self.pkg, version))

    def test_initial_import(self):
        """Test that importing into an empty repo works"""
        repo = GitRepository.create(self.pkg)
        os.chdir(self.pkg)
        orig = self._orig('2.6')
        ok_(import_orig(['arg0', '--no-interactive', '--pristine-tar', orig]) == 0)

        self._check_repo_state(repo, 'master', self.def_branches,
                               tags=['upstream/2.6'])

    def test_tag_exists(self):
        """Test that importing an already importet version fails"""
        repo = GitRepository.create(self.pkg)
        os.chdir(self.pkg)
        orig = self._orig('2.6')
        # First import
        ok_(import_orig(['arg0', '--no-interactive', '--pristine-tar', orig]) == 0)
        heads = self.rem_refs(repo, self.def_branches)
        # Second import must fail
        ok_(import_orig(['arg0', '--no-interactive', '--pristine-tar', orig]) == 1)
        self._check_log(0, "gbp:error: Upstream tag 'upstream/2.6' already exists")
        # Check that the second import didn't change any refs
        self.check_refs(repo, heads)
