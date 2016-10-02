# vim: set fileencoding=utf-8 :
#
# (C) 2015,2016 Guido Günther <agx@sigxcpu.org>
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

from nose.tools import ok_, eq_, assert_false, assert_true

from gbp.scripts.import_dsc import main as import_dsc
from gbp.scripts.buildpackage import main as buildpackage


class TestBuildpackage(ComponentTestBase):
    """Test building a debian package"""

    @staticmethod
    def _dsc_name(pkg, version, dir):
        return os.path.join(DEB_TEST_DATA_DIR,
                            dir,
                            '%s_%s.dsc' % (pkg, version))

    def _test_buildpackage(self, pkg, dir, version, opts=[]):
        dsc = self._dsc_name(pkg, version, dir)
        assert import_dsc(['arg0', dsc]) == 0
        ComponentTestGitRepository(pkg)
        prebuild_out = os.path.join(os.path.abspath(pkg), 'prebuild.out')
        postbuild_out = os.path.join(os.path.abspath(pkg), 'postbuild.out')
        os.chdir(pkg)

        args = ['arg0',
                '--git-prebuild=printenv > %s' % prebuild_out,
                '--git-postbuild=printenv > %s' % postbuild_out,
                '--git-builder=/bin/true',
                '--git-cleaner=/bin/true'] + opts
        ret = buildpackage(args)
        ok_(ret == 0, "Building the package failed")
        eq_(os.path.exists(prebuild_out), True)
        eq_(os.path.exists(postbuild_out), True)

        self.check_hook_vars('prebuild', ["GBP_BUILD_DIR",
                                          "GBP_GIT_DIR",
                                          "GBP_BUILD_DIR"])

        self.check_hook_vars('postbuild', ["GBP_CHANGES_FILE",
                                           "GBP_BUILD_DIR",
                                           "GBP_CHANGES_FILE",
                                           "GBP_BUILD_DIR"])

    def test_debian_buildpackage(self):
        """Test that building a native debian package works"""
        self._test_buildpackage('git-buildpackage', 'dsc-native', '0.4.14')

    def test_non_native_buildpackage(self):
        """Test that building a source 3.0 debian package works"""
        self._test_buildpackage('hello-debhelper', 'dsc-3.0', '2.8-1')

    def test_tag_only(self):
        """Test that only tagging a native debian package works"""
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-native',
                                'git-buildpackage_%s.dsc' % version)

        dsc = _dsc('0.4.14')
        assert import_dsc(['arg0', dsc]) == 0
        repo = ComponentTestGitRepository('git-buildpackage')
        os.chdir('git-buildpackage')
        repo.delete_tag('debian/0.4.14')  # make sure we can tag again
        ret = buildpackage(['arg0',
                            '--git-tag-only',
                            '--git-posttag=printenv > posttag.out',
                            '--git-builder=touch builder-run.stamp',
                            '--git-cleaner=/bin/true'])
        ok_(ret == 0, "Building the package failed")
        eq_(os.path.exists('posttag.out'), True)
        eq_(os.path.exists('builder-run.stamp'), False)
        self.check_hook_vars('posttag', [("GBP_TAG", "debian/0.4.14"),
                                         ("GBP_BRANCH", "master"),
                                         "GBP_SHA1"])

    def test_component_generation(self):
        """Test that generating tarball and additional tarball works without pristine-tar"""
        pkg = 'hello-debhelper'
        dsc = self._dsc_name(pkg, '2.8-1', 'dsc-3.0-additional-tarballs')
        tarballs = ["../%s_2.8.orig-foo.tar.gz" % pkg,
                    "../%s_2.8.orig.tar.gz" % pkg]

        assert import_dsc(['arg0', '--no-pristine-tar', dsc]) == 0
        repo = ComponentTestGitRepository(pkg)
        os.chdir(pkg)
        assert_false(repo.has_branch('pristine-tar'), "Pristine-tar branch must not exist")
        for t in tarballs:
            self.assertFalse(os.path.exists(t), "Tarball %s must not exist" % t)
        ret = buildpackage(['arg0',
                            '--git-component=foo',
                            '--git-no-pristine-tar',
                            '--git-posttag=printenv > posttag.out',
                            '--git-builder=touch builder-run.stamp',
                            '--git-cleaner=/bin/true'])
        ok_(ret == 0, "Building the package failed")
        for t in tarballs:
            self.assertTrue(os.path.exists(t), "Tarball %s not found" % t)

    def test_pristinetar_component_generation(self):
        """Test that generating tarball and additional tarball works with pristine-tar"""
        pkg = 'hello-debhelper'
        dsc = self._dsc_name(pkg, '2.8-1', 'dsc-3.0-additional-tarballs')
        tarballs = ["../%s_2.8.orig-foo.tar.gz" % pkg,
                    "../%s_2.8.orig.tar.gz" % pkg]

        assert import_dsc(['arg0', '--pristine-tar', dsc]) == 0
        repo = ComponentTestGitRepository(pkg)
        os.chdir(pkg)
        assert_true(repo.has_branch('pristine-tar'), "Pristine-tar branch must exist")
        for t in tarballs:
            self.assertFalse(os.path.exists(t), "Tarball %s must not exist" % t)
        ret = buildpackage(['arg0',
                            '--git-component=foo',
                            '--git-pristine-tar',
                            '--git-posttag=printenv > posttag.out',
                            '--git-builder=touch builder-run.stamp',
                            '--git-cleaner=/bin/true'])
        ok_(ret == 0, "Building the package failed")
        for t in tarballs:
            self.assertTrue(os.path.exists(t), "Tarball %s not found" % t)

    def test_export_dir_buildpackage(self):
        """Test that building with a export dir works"""
        self._test_buildpackage('hello-debhelper',
                                'dsc-3.0',
                                '2.8-1',
                                ['--git-export-dir=../foo'],
                                )
        ok_(os.path.exists('../foo'))
