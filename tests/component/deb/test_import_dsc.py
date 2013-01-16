# vim: set fileencoding=utf-8 :
#
# (C) 2013 Guido Günther <agx@sigxcpu.org>
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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os

from tests.component import (ComponentTestBase,
                             ComponentTestGitRepository)
from tests.component.deb import DEB_TEST_DATA_DIR

from gbp.scripts.import_dsc import main as import_dsc

class TestImportDsc(ComponentTestBase):
    """Test importing of src.rpm files"""

    def test_debian_import(self):
        """Test that importing of debian native packages works"""
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-native',
                                'git-buildpackage_%s.dsc' % version)

        dsc = _dsc('0.4.14')
        assert import_dsc(['arg0', dsc]) == 0
        repo = ComponentTestGitRepository('git-buildpackage')
        self._check_repo_state(repo, 'master', ['master'])
        assert len(repo.get_commits()) == 1

        os.chdir('git-buildpackage')
        dsc = _dsc('0.4.15')
        assert import_dsc(['arg0', dsc]) == 0
        self._check_repo_state(repo, 'master', ['master'])
        assert len(repo.get_commits()) == 2

        dsc = _dsc('0.4.16')
        assert import_dsc(['arg0', dsc]) == 0
        self._check_repo_state(repo, 'master', ['master'])
        assert len(repo.get_commits()) == 3
