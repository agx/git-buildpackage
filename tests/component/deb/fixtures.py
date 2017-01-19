# vim: set fileencoding=utf-8 :
#
# (C) 2017 Guido Guenther <agx@sigxcpu.org>
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

from functools import wraps
from tests.component import (ComponentTestBase,
                             ComponentTestGitRepository)
from tests.component.deb import DEB_TEST_DATA_DIR

from nose.tools import eq_

from gbp.deb.dscfile import DscFile
from gbp.scripts.import_dsc import main as import_dsc

DEFAULT_NATIVE = os.path.join(DEB_TEST_DATA_DIR,
                              'dsc-native',
                              'git-buildpackage_%s.dsc' % '0.4.14')

DEFAULT_QUILT30 = os.path.join(DEB_TEST_DATA_DIR,
                               'dsc-3.0',
                               'hello-debhelper_%s.dsc' % '2.8-1')


class RepoFixtures(object):
    @classmethod
    def native(cls, fn, dsc=DEFAULT_NATIVE):
        """Debian native test fixture"""
        @wraps(fn)
        def _native_repo(*args):
            repo = cls.import_native(dsc)
            return fn(*args, repo=repo)
        return _native_repo

    @classmethod
    def quilt30(cls, fn, dsc=DEFAULT_QUILT30):
        @wraps(fn)
        def _quilt30_repo(*args):
            repo = cls.import_quilt30(dsc)
            return fn(*args, repo=repo)
        return _quilt30_repo

    @classmethod
    def import_native(cls, dsc=DEFAULT_NATIVE):
        assert import_dsc(['arg0', dsc]) == 0
        parsed = DscFile(dsc)
        repo = ComponentTestGitRepository(parsed.pkg)
        ComponentTestBase._check_repo_state(repo, 'master', ['master'])
        eq_(len(repo.get_commits()), 1)
        return repo

    @classmethod
    def import_quilt30(cls, dsc=DEFAULT_QUILT30):
        assert import_dsc(['arg0', dsc]) == 0
        parsed = DscFile(dsc)
        repo = ComponentTestGitRepository(parsed.pkg)
        ComponentTestBase._check_repo_state(repo, 'master', ['master',
                                                             'upstream'])
        eq_(len(repo.get_commits()), 2)
        return repo
        assert eq_(len(repo.get_commits()), 2)
        return repo
