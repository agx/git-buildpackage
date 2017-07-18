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
from tests.component.deb import DEB_TEST_DATA_DIR
from nose.tools import ok_

from gbp.scripts.import_dscs import main as import_dscs


class TestImportDscs(ComponentTestBase):
    """Test importing of debian source packages"""

    def test_import_debian_native(self):
        """Test that importing of debian native packages works"""
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-native',
                                'git-buildpackage_%s.dsc' % version)

        dsc1 = _dsc('0.4.14')
        dsc2 = _dsc('0.4.15')
        assert import_dscs(['arg0', dsc1, dsc2]) == 0
        repo = ComponentTestGitRepository('git-buildpackage')
        self._check_repo_state(repo, 'master', ['master'])
        assert len(repo.get_commits()) == 2
        commitmsg = repo.get_commit_info('HEAD')['body']
        ok_("git-buildpackage (0.4.15) unstable; urgency=low" in commitmsg)
