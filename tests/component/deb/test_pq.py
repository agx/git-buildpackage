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

from tests.component import (ComponentTestBase)

from tests.component.deb import DEB_TEST_DATA_DIR
from tests.component.deb.fixtures import RepoFixtures

from nose.tools import ok_, eq_

from gbp.scripts.pq import main as pq
from gbp.scripts.import_dsc import main as import_dsc


class TestPq(ComponentTestBase):
    """Test gbp pq"""

    def _test_pq(self, repo, action, opts=[]):
        args = ['arg0', action] + opts
        os.chdir(os.path.abspath(repo.path))
        ret = pq(args)
        ok_(ret == 0, "Running gbp pq %s failed" % action)

    @RepoFixtures.quilt30()
    def test_rebase_import(self, repo):
        """Test that rebase imports patches first"""
        eq_(repo.branch, 'master')
        eq_(repo.has_branch('patch-queue/master'), False)
        self._test_pq(repo, 'rebase')
        eq_(repo.has_branch('patch-queue/master'), True)

    @RepoFixtures.quilt30()
    def test_switch_import(self, repo):
        """Test that switch imports patches first"""
        eq_(repo.branch, 'master')
        eq_(repo.has_branch('patch-queue/master'), False)
        self._test_pq(repo, 'switch')
        eq_(repo.has_branch('patch-queue/master'), True)

    @RepoFixtures.quilt30()
    def test_empty_cycle(self, repo):
        eq_(repo.has_branch('patch-queue/master'), False)
        eq_(repo.branch, 'master')
        self._test_pq(repo, 'import')
        eq_(repo.has_branch('patch-queue/master'), True)
        eq_(repo.branch, 'patch-queue/master')
        self._test_pq(repo, 'rebase')
        eq_(repo.branch, 'patch-queue/master')
        self._test_pq(repo, 'export')
        eq_(repo.has_branch('patch-queue/master'), True)
        eq_(repo.branch, 'master')
        self._test_pq(repo, 'drop')
        eq_(repo.has_branch('patch-queue/master'), False)

    @RepoFixtures.quilt30()
    def test_rename(self, repo):
        patch = os.path.join(repo.path, 'debian/patches/0001-Rename.patch')

        repo.set_config('diff.renames', 'true')
        self._test_pq(repo, 'import')
        repo.rename_file('configure.ac', 'renamed')
        repo.commit_all("Rename")
        self._test_pq(repo, 'export')
        self.assertTrue(
            os.path.exists(patch))
        # Check the file was removed and added, not renamed
        with open(patch) as f:
            self.assertTrue('rename from' not in f.read())
            self.assertTrue('rename to' not in f.read())

    @staticmethod
    def _dsc_name(pkg, version, dir):
        return os.path.join(DEB_TEST_DATA_DIR,
                            dir,
                            '%s_%s.dsc' % (pkg, version))

    @staticmethod
    def _append_patch(repo, name, contents):
        with open(os.path.join(repo.path, 'debian/patches/series'), 'a') as series_file:
            series_file.write('{}.patch\n'.format(name))

        with open(os.path.join(repo.path, 'debian/patches/{}.patch'.format(name)), 'w') as patch:
            patch.write(contents)

        repo.add_files('debian/patches/{}.patch'.format(name))
        repo.commit_files(msg='Add patch: {}.patch'.format(name),
                          files=['debian/patches/series',
                                 'debian/patches/{}.patch'.format(name)])

    @RepoFixtures.quilt30()
    def test_import(self, repo):
        pkg = 'hello-debhelper'
        dsc = self._dsc_name(pkg, '2.6-2', 'dsc-3.0')
        eq_(import_dsc(['arg0', dsc]), 0)
        self._test_pq(repo, 'import')

        author, subject = repo.get_head_author_subject()
        eq_(author, 'Santiago Vila <sanvila@debian.org>')
        eq_(subject, 'Modified doc/Makefile.in to avoid '
                     '/usr/share/info/dir.gz')

        self._test_pq(repo, 'switch')

        self._append_patch(repo, 'foo', '''\
Author: Mr. T. St <t@example.com>
Description: Short DEP3 description
 Long DEP3 description
 .
 Continued
--- /dev/null
+++ b/foo
@@ -0,0 +1 @@
+foo
''')
        self._test_pq(repo, 'import', ['--force'])

        author, subject = repo.get_head_author_subject()
        eq_(subject, 'Short DEP3 description')
        eq_(author, '"Mr. T. St" <t@example.com>')

    @RepoFixtures.quilt30()
    def test_import_poor_dep3_behaviour(self, repo):
        """Demonstrate the issues with the current DEP3 support"""

        pkg = 'hello-debhelper'
        dsc = self._dsc_name(pkg, '2.6-2', 'dsc-3.0')
        eq_(import_dsc(['arg0', dsc]), 0)

        self._append_patch(repo, 'foo', '''\
Author: Mr. T. St <t@example.com>
Description: A very long description with wrapp-
  ing to increase readability in the file, which
  is currently split into a short and long description.
Origin: https://twitter.com/MrT/status/941789967361097728
Forwarded: not-needed
--- /dev/null
+++ b/foo
@@ -0,0 +1 @@
+foo
''')
        self._test_pq(repo, 'import', ['--force'])

        _, subject = repo.get_head_author_subject()
        eq_(subject, 'A very long description with wrapp-')

        self._test_pq(repo, 'export')

        relevant_parts_of_patch = ''
        with open('debian/patches/foo.patch') as patch_file:
            for line in patch_file:
                # skip the date as it's currently set to now(),
                # not a deterministic value
                if line.startswith('Date: '):
                    continue

                # stop reading after the main part of the description;
                # i.e. ignore the bit that git(1) fully controls.
                if line.startswith('---'):
                    break

                relevant_parts_of_patch += line

        eq_(relevant_parts_of_patch, '''\
From: "Mr. T. St" <t@example.com>
Subject: A very long description with wrapp-

Origin: https://twitter.com/MrT/status/941789967361097728
Forwarded: not-needed

 ing to increase readability in the file, which
 is currently split into a short and long description.
''')
