# vim: set fileencoding=utf-8 :
#
# (C) 2013,2014,2015 Guido Günther <agx@sigxcpu.org>
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
                             ComponentTestGitRepository,
                             skipUnless)
from tests.component.deb import DEB_TEST_DATA_DIR, DEB_TEST_DOWNLOAD_URL

from nose.tools import ok_, eq_

from gbp.scripts.import_dsc import main as import_dsc
from gbp.deb.pristinetar import DebianPristineTar
from gbp.deb.dscfile import DscFile


class TestImportDsc(ComponentTestBase):
    """Test importing of debian source packages"""

    def test_import_debian_native(self):
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

    @skipUnless(os.getenv("GBP_NETWORK_TESTS"), "network tests disabled")
    def test_download(self):
        def _dsc(version):
            return os.path.join(DEB_TEST_DOWNLOAD_URL,
                                'dsc-native',
                                'git-buildpackage_%s.dsc' % version)
        dsc = _dsc('0.4.14')
        assert import_dsc(['arg0',
                           '--allow-unauthenticated',
                           dsc]) == 0
        repo = ComponentTestGitRepository('git-buildpackage')
        self._check_repo_state(repo, 'master', ['master'])
        assert len(repo.get_commits()) == 1

    @skipUnless(os.getenv("GBP_NETWORK_TESTS"), "network tests disabled")
    def test_broken_download(self):
        def _not_a_dsc(version):
            return os.path.join(DEB_TEST_DOWNLOAD_URL,
                                'dsc-3.0',
                                'hello-debhelper_%s.orig.tar.gz' % version)

        f = _not_a_dsc('2.6')
        assert import_dsc(['arg0',
                           '--allow-unauthenticated',
                           f]) == 1
        self._check_log(-1, "gbp:error: Did not find a dsc file at")

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
        reflog, ret = repo._git_getoutput('reflog')
        ok_("gbp: Import Debian patch" in reflog[1])
        ok_("gbp: Import Upstream version 2.6" in reflog[2])
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

    def test_import_multiple_pristine_tar(self):
        """Test if importing a multiple tarball package works"""
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-3.0-additional-tarballs',
                                'hello-debhelper_%s.dsc' % version)

        dscfile = _dsc('2.8-1')
        assert import_dsc(['arg0',
                           '--verbose',
                           '--pristine-tar',
                           '--debian-branch=master',
                           '--upstream-branch=upstream',
                           dscfile]) == 0
        repo = ComponentTestGitRepository('hello-debhelper')
        self._check_repo_state(repo, 'master', ['master', 'pristine-tar', 'upstream'])
        commits, expected = len(repo.get_commits()), 2

        for file in ['foo/test1', 'foo/test2']:
            ok_(file in repo.ls_tree('HEAD'),
                "Could not find component tarball file %s in %s" % (file, repo.ls_tree('HEAD')))

        ok_(commits == expected, "Found %d commit instead of %d" % (commits, expected))

        dsc = DscFile.parse(dscfile)
        # Check if we can rebuild the tarball and component
        ptars = [('hello-debhelper_2.8.orig.tar.gz', 'pristine-tar', '', dsc.tgz),
                 ('hello-debhelper_2.8.orig-foo.tar.gz', 'pristine-tar^', 'foo', dsc.additional_tarballs['foo'])]

        p = DebianPristineTar(repo)
        outdir = os.path.abspath('.')
        for f, w, s, o in ptars:
            eq_(repo.get_subject(w), 'pristine-tar data for %s' % f)
            old = self.hash_file(o)
            p.checkout('hello-debhelper', '2.8', 'gzip', outdir, component=s)
            new = self.hash_file(os.path.join(outdir, f))
            eq_(old, new, "Checksum %s of regenerated tarball %s does not match original %s" %
                (f, old, new))

    def test_existing_dir(self):
        """
        Importing outside of git repository with existing target
        dir must fail
        """
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-3.0',
                                'hello-debhelper_%s.dsc' % version)

        # Create directory we should stumble upon
        os.makedirs('hello-debhelper')
        dsc = _dsc('2.8-1')
        assert import_dsc(['arg0',
                           '--verbose',
                           '--pristine-tar',
                           '--debian-branch=master',
                           '--upstream-branch=upstream',
                           dsc]) == 1
        self._check_log(0, "gbp:error: Directory 'hello-debhelper' already exists. If you want to import into it, "
                        "please change into this directory otherwise move it away first")

    def test_import_10(self):
        """Test if importing a 1.0 source format package works"""
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-1.0',
                                'hello-debhelper_%s.dsc' % version)

        dsc = _dsc('2.6-2')
        assert import_dsc(['arg0', dsc]) == 0
        repo = ComponentTestGitRepository('hello-debhelper')
        self._check_repo_state(repo, 'master', ['master', 'upstream'],
                               tags=['upstream/2.6', 'debian/2.6-2'])
        assert len(repo.get_commits()) == 2

    def test_target_dir(self):
        """Test if setting the target dir works"""
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-3.0',
                                'hello-debhelper_%s.dsc' % version)
        dsc = _dsc('2.6-2')
        assert import_dsc(['arg0',
                           '--verbose',
                           '--no-pristine-tar',
                           dsc,
                           'targetdir']) == 0
        assert os.path.exists('targetdir')
        repo = ComponentTestGitRepository('targetdir')
        self._check_repo_state(repo, 'master', ['master', 'upstream'])
