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

from tests.component import (ComponentTestBase,
                             ComponentTestGitRepository)
from tests.component.deb import DEB_TEST_DATA_DIR

from nose.tools import ok_

from gbp.scripts.import_dsc import main as import_dsc
from gbp.scripts.buildpackage import main as buildpackage


class TestBuildpackage(ComponentTestBase):
    """Test building a debian package"""

    def test_debian_buildpackage(self):
        """Test that building a native debian  package works"""
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-native',
                                'git-buildpackage_%s.dsc' % version)

        dsc = _dsc('0.4.14')
        assert import_dsc(['arg0', dsc]) == 0
        repo = ComponentTestGitRepository('git-buildpackage')
        os.chdir('git-buildpackage')
        ret = buildpackage(['arg0',
                            '--git-builder=/bin/true',
                            '--git-cleaner=/bin/true'])
        ok_(ret == 0, "Building the package failed")
