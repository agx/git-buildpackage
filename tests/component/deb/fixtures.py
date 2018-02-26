# vim: set fileencoding=utf-8 :
#
# (C) 2017 Guido Günther <agx@sigxcpu.org>
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

from nose.tools import eq_, ok_

from gbp.command_wrappers import UnpackTarArchive
from gbp.git import GitRepository
from gbp.deb.dscfile import DscFile
from gbp.scripts.import_dsc import main as import_dsc

DEFAULT_NATIVE = os.path.join(DEB_TEST_DATA_DIR,
                              'dsc-native',
                              'git-buildpackage_%s.dsc' % '0.4.14')

DEFAULT_QUILT30 = os.path.join(DEB_TEST_DATA_DIR,
                               'dsc-3.0',
                               'hello-debhelper_%s.dsc' % '2.8-1')

DEFAULT_ADDITIONAL_TAR = os.path.join(DEB_TEST_DATA_DIR,
                                      'dsc-3.0-additional-tarballs',
                                      'hello-debhelper_%s.dsc' % '2.8-1')

DEFAULT_OVERLAY = os.path.join(DEB_TEST_DATA_DIR,
                               'dsc-3.0-additional-tarballs',
                               'hello-debhelper_%s.debian.tar.gz' % '2.8-1')


class RepoFixtures(object):
    @classmethod
    def native(cls, dsc=DEFAULT_NATIVE, opts=None):
        """Decorator to be used as Debian native test fixture"""
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
    def quilt30_additional_tarball(cls, dsc=DEFAULT_ADDITIONAL_TAR, opts=None):
        """Decorator to be used as 3.0 (quilt) with additional tarball test fixture"""
        def wrapper(fn):
            @wraps(fn)
            def _quilt30_additional_tar_repo(*args):
                repo = cls.import_quilt30_additional_tarball(dsc, opts)
                return fn(*args, repo=repo)
            return _quilt30_additional_tar_repo
        return wrapper

    @classmethod
    def overlay(cls, debian=DEFAULT_OVERLAY, opts=None):
        """Decorator to be used as overay mode test fixture"""
        def wrapper(fn):
            @wraps(fn)
            def _overlay_mode_repo(*args):
                repo = cls.import_debian_tarball(debian, opts)
                return fn(*args, repo=repo)
            return _overlay_mode_repo
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

    @classmethod
    def import_quilt30_additional_tarball(cls, dsc=DEFAULT_ADDITIONAL_TAR, opts=None):
        """Import a 3.0 (quilt) package with additional tarball, verify and change into repo"""
        repo = cls._import_one(dsc, opts)
        expected_branches = ['master', 'upstream']
        if opts and '--pristine-tar' in opts:
            expected_branches.append('pristine-tar')
        ComponentTestBase._check_repo_state(repo, 'master', expected_branches)
        eq_(len(repo.get_commits()), 2)
        os.chdir(repo.path)
        ok_(os.path.exists('./foo'))
        return repo

    @classmethod
    def import_debian_tarball(cls, debian=DEFAULT_OVERLAY, opts=None):
        """Import a 3.0 (quilt) debian dir for overlay mode"""
        repo = GitRepository.create(os.path.split('/')[-1].split('_')[0])
        UnpackTarArchive(debian, repo.path)()
        repo.add_files('.')
        repo.commit_files('.', msg="debian dir")
        expected_branches = ['master']
        ComponentTestBase._check_repo_state(repo, 'master', expected_branches)
        eq_(len(repo.get_commits()), 1)
        os.chdir(repo.path)
        return repo
