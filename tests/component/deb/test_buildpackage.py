# vim: set fileencoding=utf-8 :
#
# (C) 2015-2017 Guido Günther <agx@sigxcpu.org>
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

import glob
import hashlib
import os
import subprocess
import tarfile

from tests.component import (ComponentTestBase,
                             ComponentTestGitRepository)
from tests.component.deb import DEB_TEST_DATA_DIR
from tests.component.deb.fixtures import (RepoFixtures,
                                          DEFAULT_OVERLAY)
from tests.testutils import skip_without_cmd

from nose.tools import ok_, eq_, assert_false, assert_true

from gbp.scripts.import_dsc import main as import_dsc
from gbp.scripts.buildpackage import main as buildpackage
from gbp.scripts.pq import main as pq

from gbp.deb.changelog import ChangeLog


class TestBuildpackage(ComponentTestBase):
    """Test building a debian package"""

    @staticmethod
    def _dsc_name(pkg, version, dir):
        return os.path.join(DEB_TEST_DATA_DIR,
                            dir,
                            '%s_%s.dsc' % (pkg, version))

    def _test_buildpackage(self, repo, opts=[]):
        prebuild_out = os.path.join(repo.path, '..', 'prebuild.out')
        postbuild_out = os.path.join(repo.path, '..', 'postbuild.out')
        args = ['arg0',
                '--git-prebuild=printenv > %s' % prebuild_out,
                '--git-postbuild=printenv > %s' % postbuild_out,
                '--git-builder=/bin/true',
                '--git-cleaner=/bin/true'] + opts
        os.chdir(repo.path)
        ret = buildpackage(args)
        ok_(ret == 0, "Building the package failed")
        eq_(os.path.exists(prebuild_out), True)
        eq_(os.path.exists(postbuild_out), True)

        self.check_hook_vars('../prebuild', ["GBP_BUILD_DIR",
                                             "GBP_GIT_DIR",
                                             "GBP_BUILD_DIR"])

        self.check_hook_vars('../postbuild', ["GBP_CHANGES_FILE",
                                              "GBP_BUILD_DIR",
                                              "GBP_CHANGES_FILE",
                                              "GBP_BUILD_DIR"])

    @RepoFixtures.native()
    def test_debian_buildpackage(self, repo):
        """Test that building a native debian package works"""
        self._test_buildpackage(repo)

    @RepoFixtures.quilt30()
    def test_non_native_buildpackage(self, repo):
        """Test that building a source 3.0 debian package works"""
        self._test_buildpackage(repo)

    @RepoFixtures.native()
    def test_tag_only(self, repo):
        """Test that only tagging a native debian package works"""
        repo.delete_tag('debian/0.4.14')  # make sure we can tag again
        ret = buildpackage(['arg0',
                            '--git-tag-only',
                            '--git-posttag=printenv > ../posttag.out',
                            '--git-builder=touch ../builder-run.stamp',
                            '--git-cleaner=/bin/true'])
        ok_(ret == 0, "Building the package failed")
        eq_(os.path.exists('../posttag.out'), True)
        eq_(os.path.exists('../builder-run.stamp'), False)
        self.check_hook_vars('../posttag', [("GBP_TAG", "debian/0.4.14"),
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
        #  Make sure the tree object for importing the main tarball is recreated
        repo.collect_garbage(prune='all', aggressive=True)
        ret = buildpackage(['arg0',
                            '--git-component=foo',
                            '--git-pristine-tar',
                            '--git-posttag=printenv > posttag.out',
                            '--git-builder=touch builder-run.stamp',
                            '--git-cleaner=/bin/true'])
        ok_(ret == 0, "Building the package failed")
        for t in tarballs:
            self.assertTrue(os.path.exists(t), "Tarball %s not found" % t)

    @RepoFixtures.quilt30()
    def test_pristine_tar_commit(self, repo):
        """Test that committing to pristine-tar branch after building tarballs works"""
        assert_false(repo.has_branch('pristine-tar'), "Pristine-tar branch must not exist")
        ret = buildpackage(['arg0',
                            '--git-builder=/bin/true',
                            '--git-pristine-tar-commit'])
        ok_(ret == 0, "Building the package failed")
        assert_true(repo.has_branch('pristine-tar'), "Pristine-tar branch must exist")
        eq_(repo.ls_tree('pristine-tar'), {b'hello-debhelper_2.8.orig.tar.gz.id',
                                           b'hello-debhelper_2.8.orig.tar.gz.delta'})

    @RepoFixtures.quilt30()
    def test_sloppy_tarball_generation(self, repo):
        """Test that generating tarball from Debian branch works"""
        tarball = '../hello-debhelper_2.8.orig.tar.gz'
        self.add_file(repo, 'foo.txt')
        self._test_buildpackage(repo, ['--git-force-create',
                                       '--git-upstream-tree=SLOPPY'])
        self.assertTrue(os.path.exists(tarball))
        t = tarfile.open(name=tarball, mode="r:gz")
        names = t.getnames()
        for f in ['hello-debhelper-2.8/build-aux',
                  'hello-debhelper-2.8/foo.txt']:
            self.assertIn(f, names)
        self.assertNotIn('hello-debhelper-2.8/debian', names)

    @RepoFixtures.quilt30()
    def test_export_dir_buildpackage(self, repo):
        """Test that building with a export dir works"""
        self._test_buildpackage(repo, ['--git-export-dir=../foo/bar'])
        ok_(os.path.exists('../foo/bar'))

    @RepoFixtures.quilt30_additional_tarball()
    def test_export_dir_additional_tar(self, repo):
        """Test that building with a export dir and additional tarball works"""
        self._test_buildpackage(repo, ['--git-export-dir=../foo/bar',
                                       '--git-no-purge',
                                       '--git-component=foo'])
        # Check that all needed tarballs end up in the build-area
        eq_(sorted(glob.glob('../foo/bar/*')), ['../foo/bar/hello-debhelper-2.8',
                                                '../foo/bar/hello-debhelper_2.8.orig-foo.tar.gz',
                                                '../foo/bar/hello-debhelper_2.8.orig.tar.gz'])
        # Check that directories from additional tarballs get exported too
        ok_(os.path.exists('../foo/bar/hello-debhelper-2.8/foo'))

    @RepoFixtures.overlay()
    def test_export_dir_overlay(self, repo):
        """Test that building in overlay mode with export dir works"""
        tarball_dir = os.path.dirname(DEFAULT_OVERLAY)
        self._test_buildpackage(repo, ['--git-overlay',
                                       '--git-compression=auto',
                                       '--git-tarball-dir=%s' % tarball_dir,
                                       '--git-no-purge',
                                       '--git-component=foo',
                                       '--git-export-dir=../overlay'])
        # Check if main tarball got unpacked
        ok_(os.path.exists('../overlay/hello-debhelper-2.8/configure'))
        # Check if debian dir is there
        ok_(os.path.exists('../overlay/hello-debhelper-2.8/debian/changelog'))
        # Check if additional tarball got unpacked
        ok_(os.path.exists('../overlay/hello-debhelper-2.8/foo/test1'))
        # Check if upstream tarballs is in export_dir
        eq_(sorted(glob.glob('../overlay/*')), ['../overlay/hello-debhelper-2.8',
                                                '../overlay/hello-debhelper_2.8.orig-foo.tar.gz',
                                                '../overlay/hello-debhelper_2.8.orig.tar.gz'])

    @RepoFixtures.quilt30()
    def test_export_wc_buildpackage(self, repo):
        """Test that exporting working copy works and it ignores
        modifications the source tree """
        with open(os.path.join(repo.path, 'foo.txt'), 'w') as f:
            f.write("foo")
        self._test_buildpackage(repo, ['--git-export=WC',
                                       '--git-export-dir=../foo/bar'])
        ok_(os.path.exists('../foo/bar'))

    @RepoFixtures.native()
    def test_argument_quoting(self, repo):
        """Test that we quote arguments to builder (#850869)"""
        with open('../arg with spaces', 'w'):
            pass
        # We use ls as builder to look for a file with spaces. This
        # will fail if build arguments are not properly quoted and
        # therefore split up
        ret = buildpackage(['arg0',
                            '--git-builder=ls',
                            '--git-cleaner=/bin/true',
                            '../arg with spaces'])
        ok_(ret == 0, "Building the package failed")

    @RepoFixtures.quilt30()
    def test_tarball_default_compression(self, repo):
        """Test that we use defaults for compression if not given (#820846)"""
        self._test_buildpackage(repo, ['--git-no-pristine-tar'])
        tarball = "../hello-debhelper_2.8.orig.tar.gz"
        out = subprocess.check_output(["file", tarball])
        ok_(b"max compression" not in out)
        m1 = hashlib.md5(open(tarball, 'rb').read()).hexdigest()
        os.unlink(tarball)
        eq_(buildpackage(['arg0',
                          '--git-ignore-new',
                          '--git-builder=/bin/true',
                          '--git-cleaner=/bin/true',
                          '../arg with spaces']), 0)
        m2 = hashlib.md5(open(tarball, 'rb').read()).hexdigest()
        eq_(m1, m2, "Regenerated tarball has different checksum")

    @RepoFixtures.quilt30()
    def test_tarball_max_compression(self, repo):
        """Test that passing max compression works (#820846)"""
        self._test_buildpackage(repo, ['--git-no-pristine-tar', '--git-compression-level=9'])
        out = subprocess.check_output(["file", "../hello-debhelper_2.8.orig.tar.gz"])
        ok_(b"max compression" in out)

    @RepoFixtures.quilt30()
    def test_tag_pq_branch(self, repo):
        ret = pq(['argv0', 'import'])
        eq_(repo.rev_parse('master'), repo.rev_parse('debian/2.8-1^{}'))
        eq_(ret, 0)
        eq_(repo.branch, 'patch-queue/master')
        self.add_file(repo, 'foo.txt')
        ret = buildpackage(['argv0',
                            '--git-tag-only',
                            '--git-retag',
                            '--git-ignore-branch'])
        eq_(ret, 0)
        eq_(repo.branch, 'patch-queue/master')
        eq_(repo.rev_parse('patch-queue/master^{}^'), repo.rev_parse('debian/2.8-1^{}'))

    @RepoFixtures.quilt30()
    def test_tag_detached_head(self, repo):
        """
        Test that tagging works with an detached head (#863167)
        """
        eq_(repo.rev_parse('master^{}'), repo.rev_parse('debian/2.8-1^{}'))
        self.add_file(repo, 'debian/foo.txt')
        repo.checkout("HEAD~")
        ret = buildpackage(['argv0',
                            '--git-tag-only',
                            '--git-retag',
                            '--git-ignore-branch'])
        eq_(ret, 0)
        repo.checkout("master")
        eq_(repo.rev_parse('master~^{}'), repo.rev_parse('debian/2.8-1^{}'))

    @skip_without_cmd('debchange')
    @RepoFixtures.quilt30()
    def test_broken_upstream_version(self, repo):
        cl = ChangeLog(filename='debian/changelog')
        cl.add_section(["broken versionnumber"],
                       "unstable",
                       version={'version': "3.0"})
        ret = buildpackage(['argv0',
                            '--git-ignore-new',
                            '--git-builder=/bin/true',
                            '--git-tarball-dir=../tarballs'])
        eq_(ret, 1)
        self._check_log(-1, "gbp:error: Non-native package 'hello-debhelper' has invalid version '3.0'")

    @RepoFixtures.quilt30()
    def test_preexport(self, repo):
        """Test the pre-export hook """
        preexport_out = os.path.join(repo.path, '..', 'preexport.out')
        self._test_buildpackage(repo, ['--git-export-dir=../export-dir',
                                       '--git-preexport=printenv > %s' % preexport_out])
        ok_(os.path.exists(preexport_out))
        self.check_hook_vars('../preexport', ["GBP_BUILD_DIR", "GBP_GIT_DIR"])

    @RepoFixtures.overlay()
    def test_export_dir_version_replacement(self, repo):
        """Test that building in overlay mode with export dir with versioned name works"""
        tarball_dir = os.path.join(DEB_TEST_DATA_DIR, 'foo-%(version)s')
        self._test_buildpackage(repo, ['--git-overlay',
                                       '--git-compression=auto',
                                       '--git-tarball-dir=%s' % tarball_dir,
                                       '--git-no-purge',
                                       '--git-component=foo',
                                       '--git-export-dir=../foo'])
        # Check if main tarball got unpacked
        ok_(os.path.exists('../foo/hello-debhelper-2.8/configure'))
        # Check if debian dir is there
        ok_(os.path.exists('../foo/hello-debhelper-2.8/debian/changelog'))
        # Check if additional tarball got unpacked
        ok_(os.path.exists('../foo/hello-debhelper-2.8/foo/test1'))
        # Check if upstream tarballs is in export_dir
        eq_(sorted(glob.glob('../foo/*')), ['../foo/hello-debhelper-2.8',
                                            '../foo/hello-debhelper_2.8.orig-foo.tar.gz',
                                            '../foo/hello-debhelper_2.8.orig.tar.gz'])
