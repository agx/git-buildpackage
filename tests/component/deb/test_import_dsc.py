# vim: set fileencoding=utf-8 :
#
# (C) 2013,2014 Guido Günther <agx@sigxcpu.org>
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

class TestImportDsc(ComponentTestBase):
    """Test importing of debian source packages"""

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

    def test_create_branches(self):
        """Test if creating missing branches works"""
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-3.0',
                                'hello-debhelper_%s.dsc' % version)

        dsc = _dsc('2.6-2')
        assert import_dsc(['arg0',
                           '--verbose',
                           '--pristine-tar',
                           '--debian-branch=master',
                           '--upstream-branch=upstream',
                           dsc]) == 0
        repo = ComponentTestGitRepository('hello-debhelper')
        os.chdir('hello-debhelper')
        assert len(repo.get_commits()) == 2
        self._check_repo_state(repo, 'master', ['master', 'pristine-tar', 'upstream'])
        dsc = _dsc('2.8-1')
        assert import_dsc(['arg0',
                           '--verbose',
                           '--pristine-tar',
                           '--debian-branch=foo',
                           '--upstream-branch=bar',
                           '--create-missing-branches',
                           dsc]) == 0
        self._check_repo_state(repo, 'master', ['bar', 'foo', 'master', 'pristine-tar', 'upstream'])
        commits, expected = len(repo.get_commits()), 2
        ok_(commits == expected, "Found %d commit instead of %d" % (commits, expected))
