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
    def native(cls, dsc=DEFAULT_NATIVE, opts=None):
        """Docorator to be used as Debian native test fixture"""
        def wrapper(fn):
            @wraps(fn)
            def _native_repo(*args):
                repo = cls.import_native(dsc, opts)
                return fn(*args, repo=repo)
            return _native_repo
        return wrapper

    @classmethod
    def quilt30(cls, dsc=DEFAULT_QUILT30, opts=None):
        """Decorator to be used as 3.0 (quilt) test fixture"""
        def wrapper(fn):
            @wraps(fn)
            def _quilt30_repo(*args):
                repo = cls.import_quilt30(dsc, opts)
                return fn(*args, repo=repo)
            return _quilt30_repo
        return wrapper

    @classmethod
    def _import_one(cls, dsc, opts):
        opts = opts or []
        assert import_dsc(['arg0'] + opts + [dsc]) == 0
        parsed = DscFile(dsc)
        return ComponentTestGitRepository(parsed.pkg)

    @classmethod
    def import_native(cls, dsc=DEFAULT_NATIVE, opts=None):
        """Import a Debian native package, verify and change into repo"""
        repo = cls._import_one(dsc, opts)
        ComponentTestBase._check_repo_state(repo, 'master', ['master'])
        eq_(len(repo.get_commits()), 1)
        os.chdir(repo.path)
        return repo

    @classmethod
    def import_quilt30(cls, dsc=DEFAULT_QUILT30, opts=None):
        """Import a 3.0 (quilt)  package, verify and change into repo"""
        repo = cls._import_one(dsc, opts)
        expected_branches = ['master', 'upstream']
        if opts and '--pristine-tar' in opts:
            expected_branches.append('pristine-tar')
        ComponentTestBase._check_repo_state(repo, 'master', expected_branches)
        eq_(len(repo.get_commits()), 2)
        os.chdir(repo.path)
        return repo
