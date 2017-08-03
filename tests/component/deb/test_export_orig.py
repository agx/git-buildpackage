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

from nose.tools import ok_, assert_false, assert_true

from gbp.scripts.import_dsc import main as import_dsc
from gbp.scripts.export_orig import main as export_orig


class TestExportOrig(ComponentTestBase):
    """Test exporting of orig tarballs"""

    @staticmethod
    def _dsc_name(pkg, version, dir):
        return os.path.join(DEB_TEST_DATA_DIR,
                            dir,
                            '%s_%s.dsc' % (pkg, version))

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
        ret = export_orig(['arg0',
                           '--component=foo',
                           '--no-pristine-tar'])
        ok_(ret == 0, "Exporting tarballs failed")
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
        ret = export_orig(['arg0',
                           '--component=foo',
                           '--pristine-tar'])
        ok_(ret == 0, "Exporting tarballs failed")
        for t in tarballs:
            self.assertTrue(os.path.exists(t), "Tarball %s not found" % t)

    def test_git_archive_tree_non_existent(self):
        """Test that we're tarball generation when commits are missing"""
        pkg = 'hello-debhelper'
        dsc = self._dsc_name(pkg, '2.8-1', 'dsc-3.0-additional-tarballs')

        assert import_dsc(['arg0', '--no-pristine-tar', dsc]) == 0
        repo = ComponentTestGitRepository(pkg)
        os.chdir(pkg)
        assert_false(repo.has_branch('pristine-tar'), "Pristine-tar branch not must exist")
        ret = export_orig(['arg0',
                           '--component=bar',  # non-existing component
                           '--no-pristine-tar'])
        ok_(ret == 1, "Exporting tarballs must fail")
        self._check_log(-1, "gbp:error: No tree for 'bar' found in "
                        "'upstream/2.8' to create additional tarball from")

    def test_pristine_tar_commit_non_existent(self):
        """Test that we're failing if pristine-tar commit is missing"""
        pkg = 'hello-debhelper'
        dsc = self._dsc_name(pkg, '2.8-1', 'dsc-3.0-additional-tarballs')

        assert import_dsc(['arg0', '--pristine-tar', dsc]) == 0
        repo = ComponentTestGitRepository(pkg)
        os.chdir(pkg)
        assert_true(repo.has_branch('pristine-tar'), "Pristine-tar branch must exist")
        repo.delete_branch("pristine-tar")
        repo.create_branch("pristine-tar")  # create a nonsense pristine-tar branch
        ret = export_orig(['arg0',
                           '--component=foo',
                           '--pristine-tar'])
        ok_(ret == 1, "Exporting tarballs must fail")
        self._check_log(-1, ".*git show refs/heads/pristine-tar:.*failed")
