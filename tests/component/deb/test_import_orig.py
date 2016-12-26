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

from mock import patch, DEFAULT

from tests.component import (ComponentTestBase,
                             ComponentTestGitRepository,
                             skipUnless)
from tests.component.deb import DEB_TEST_DATA_DIR, DEB_TEST_DOWNLOAD_URL

from gbp.scripts.import_dsc import main as import_dsc
from gbp.scripts.import_orig import main as import_orig
from gbp.deb.pristinetar import DebianPristineTar
from gbp.deb.dscfile import DscFile
from gbp.git.repository import GitRepository, GitRepositoryError

from nose.tools import ok_, eq_


def raise_if_tag_match(match):
    def wrapped(*args, **kwargs):
        if len(args) > 0 and args[0].startswith(match) or kwargs.get('name', '').startswith(match):
            raise GitRepositoryError('this is a create tag error mock for %s %s' % (match, kwargs))
        return DEFAULT
    return wrapped


class TestImportOrig(ComponentTestBase):
    """Test importing of new upstream versions"""
    pkg = "hello-debhelper"
    def_branches = ['master', 'upstream', 'pristine-tar']

    def _orig(self, version, dir='dsc-3.0'):
        return os.path.join(DEB_TEST_DATA_DIR,
                            dir,
                            '%s_%s.orig.tar.gz' % (self.pkg, version))

    def _download_url(self, version, dir='dsc-3.0'):
        return os.path.join(DEB_TEST_DOWNLOAD_URL,
                            dir,
                            '%s_%s.orig.tar.gz' % (self.pkg, version))

    def _dsc(self, version, dir='dsc-3.0'):
        return os.path.join(DEB_TEST_DATA_DIR,
                            dir,
                            '%s_%s.dsc' % (self.pkg, version))

    def test_initial_import(self):
        """Test that importing into an empty repo works"""
        repo = GitRepository.create(self.pkg)
        os.chdir(self.pkg)
        orig = self._orig('2.6')
        ok_(import_orig(['arg0', '--no-interactive', '--pristine-tar', orig]) == 0)
        self._check_repo_state(repo, 'master', self.def_branches,
                               tags=['upstream/2.6'])

    @skipUnless(os.getenv("GBP_NETWORK_TESTS"), "network tests disabled")
    def test_download(self):
        """Test that importing via download works"""
        repo = GitRepository.create(self.pkg)
        os.chdir(self.pkg)
        orig = self._download_url('2.6')
        ok_(import_orig(['arg0', '--no-interactive', '--pristine-tar', orig]) == 0)
        self._check_repo_state(repo, 'master', self.def_branches,
                               tags=['upstream/2.6'])

    def test_update(self):
        """
        Test that importing a new version works
        """
        dsc = self._dsc('2.6-2')
        ok_(import_dsc(['arg0', '--pristine-tar', dsc]) == 0)
        repo = ComponentTestGitRepository(self.pkg)
        os.chdir(self.pkg)
        self._check_repo_state(repo, 'master', ['master', 'upstream', 'pristine-tar'])

        orig = self._orig('2.8')
        ok_(import_orig(['arg0',
                         '--postimport=printenv > postimport.out',
                         '--no-interactive', '--pristine-tar', orig]) == 0)
        self._check_repo_state(repo, 'master', ['master', 'upstream', 'pristine-tar'],
                               tags=['debian/2.6-2', 'upstream/2.6', 'upstream/2.8'])
        eq_(os.path.exists('postimport.out'), True)
        self.check_hook_vars('postimport', [("GBP_BRANCH", "master"),
                                            ("GBP_TAG", "upstream/2.8"),
                                            ("GBP_UPSTREAM_VERSION", "2.8"),
                                            ("GBP_DEBIAN_VERSION", "2.8-1")])

    def test_update_component_tarballs(self):
        """
        Test importing new version with additional tarballs works
        """
        dsc = self._dsc('2.6-2')
        ok_(import_dsc(['arg0', '--pristine-tar', dsc]) == 0)
        repo = ComponentTestGitRepository(self.pkg)
        os.chdir(self.pkg)
        self._check_repo_state(repo, 'master', ['master', 'upstream', 'pristine-tar'])

        # Import 2.8
        orig = self._orig('2.8', dir='dsc-3.0-additional-tarballs')
        ok_(import_orig(['arg0', '--component=foo', '--no-interactive', '--pristine-tar', orig]) == 0)
        self._check_repo_state(repo, 'master', ['master', 'upstream', 'pristine-tar'],
                               tags=['debian/2.6-2', 'upstream/2.6', 'upstream/2.8'])
        for file in ['foo/test1', 'foo/test2']:
            ok_(file in repo.ls_tree('HEAD'),
                "Could not find component tarball file %s in %s" % (file, repo.ls_tree('HEAD')))
            ok_(file in repo.ls_tree('upstream'),
                "Could not find component tarball file %s in %s" % (file, repo.ls_tree('HEAD')))

        dsc = DscFile.parse(self._dsc('2.8-1', dir='dsc-3.0-additional-tarballs'))
        # Check if we can rebuild the upstream tarball and additional tarball
        ptars = [('hello-debhelper_2.8.orig.tar.gz', 'pristine-tar', '', dsc.tgz),
                 ('hello-debhelper_2.8.orig-foo.tar.gz', 'pristine-tar^', 'foo', dsc.additional_tarballs['foo'])]

        p = DebianPristineTar(repo)
        outdir = os.path.abspath('.')
        for f, w, s, o in ptars:
            eq_(repo.get_subject(w), 'pristine-tar data for %s' % f)
            old = self.hash_file(o)
            p.checkout('hello-debhelper', '2.8', 'gzip', outdir, component=s)
            out = os.path.join(outdir, f)
            new = self.hash_file(out)
            eq_(old, new, "Checksum %s of regenerated tarball %s does not match original %s" %
                (f, old, new))
            os.unlink(out)

        # Import 2.9
        orig = self._orig('2.9', dir='dsc-3.0-additional-tarballs')
        ok_(import_orig(['arg0', '--component=foo', '--no-interactive', '--pristine-tar', orig]) == 0)
        self._check_repo_state(repo, 'master', ['master', 'upstream', 'pristine-tar'],
                               tags=['debian/2.6-2', 'upstream/2.6', 'upstream/2.8', 'upstream/2.9'])
        for file in ['foo/test1', 'foo/test2', 'foo/test3']:
            ok_(file in repo.ls_tree('HEAD'),
                "Could not find component tarball file %s in %s" % (file, repo.ls_tree('HEAD')))
            ok_(file in repo.ls_tree('upstream'),
                "Could not find component tarball file %s in %s" % (file, repo.ls_tree('HEAD')))

        dsc = DscFile.parse(self._dsc('2.9-1', dir='dsc-3.0-additional-tarballs'))
        # Check if we can rebuild the upstream tarball and additional tarball
        ptars = [('hello-debhelper_2.9.orig.tar.gz', 'pristine-tar', '', dsc.tgz),
                 ('hello-debhelper_2.9.orig-foo.tar.gz', 'pristine-tar^', 'foo', dsc.additional_tarballs['foo'])]

        p = DebianPristineTar(repo)
        outdir = os.path.abspath('.')
        for f, w, s, o in ptars:
            eq_(repo.get_subject(w), 'pristine-tar data for %s' % f)
            old = self.hash_file(o)
            p.checkout('hello-debhelper', '2.9', 'gzip', outdir, component=s)
            new = self.hash_file(os.path.join(outdir, f))
            eq_(old, new, "Checksum %s of regenerated tarball %s does not match original %s" %
                (f, old, new))

    def test_tag_exists(self):
        """Test that importing an already imported version fails"""
        repo = GitRepository.create(self.pkg)
        os.chdir(self.pkg)
        orig = self._orig('2.6')
        # First import
        ok_(import_orig(['arg0', '--no-interactive', '--pristine-tar', orig]) == 0)
        heads = self.rem_refs(repo, self.def_branches)
        # Second import must fail
        ok_(import_orig(['arg0', '--no-interactive', '--pristine-tar', orig]) == 1)
        self._check_log(0, "gbp:error: Upstream tag 'upstream/2.6' already exists")
        # Check that the second import didn't change any refs
        self.check_refs(repo, heads)

    def test_update_fail_create_upstream_tag(self):
        """
        Test that we can recover from a failure to create the upstream
        tag
        """
        repo = GitRepository.create(self.pkg)
        os.chdir(self.pkg)

        dsc = self._dsc('2.6-2')
        ok_(import_dsc(['arg0', '--pristine-tar', dsc]) == 0)
        self._check_repo_state(repo, 'master', ['master', 'upstream', 'pristine-tar'])

        heads = self.rem_refs(repo, self.def_branches)

        orig = self._orig('2.8')
        with patch('gbp.git.repository.GitRepository.create_tag',
                   side_effect=GitRepositoryError('this is a create tag error mock')):
            ok_(import_orig(['arg0', '--no-interactive', '--pristine-tar', orig]) == 1)
        self._check_repo_state(repo, 'master', ['master', 'upstream', 'pristine-tar'],
                               tags=['debian/2.6-2', 'upstream/2.6'])
        self.check_refs(repo, heads)

    def test_update_fail_merge(self):
        """
        Test that we can recover from a failed merge
        """
        repo = GitRepository.create(self.pkg)
        os.chdir(self.pkg)

        dsc = self._dsc('2.6-2')
        ok_(import_dsc(['arg0', '--pristine-tar', dsc]) == 0)
        self._check_repo_state(repo, 'master', ['master', 'upstream', 'pristine-tar'])

        heads = self.rem_refs(repo, self.def_branches)

        orig = self._orig('2.8')
        with patch('gbp.scripts.import_orig.debian_branch_merge',
                   side_effect=GitRepositoryError('this is a fail merge error mock')):
            ok_(import_orig(['arg0', '--no-interactive', '--pristine-tar', orig]) == 1)
        self._check_repo_state(repo, 'master', ['master', 'upstream', 'pristine-tar'],
                               tags=['debian/2.6-2', 'upstream/2.6'])
        self.check_refs(repo, heads)

    @patch('gbp.git.repository.GitRepository.create_tag',
           side_effect=raise_if_tag_match('upstream/'))
    def test_initial_import_fail_create_upstream_tag(self, RepoMock):
        """
        Test that we can recover from a failure to create the upstream
        tag on initial import
        """
        repo = GitRepository.create(self.pkg)
        os.chdir(self.pkg)
        orig = self._orig('2.6')
        ok_(import_orig(['arg0', '--no-interactive', orig]) == 1)

        self._check_repo_state(repo, None, [], tags=[])

    def test_initial_import_fail_create_debian_branch(self):
        """
        Test that we can recover from creating the Debian branch on
        initial import
        """
        repo = GitRepository.create(self.pkg)
        os.chdir(self.pkg)
        orig = self._orig('2.6')

        with patch('gbp.git.repository.GitRepository.create_branch',
                   side_effect=GitRepositoryError('this is a create branch error mock')):
            ok_(import_orig(['arg0', '--no-interactive', '--pristine-tar', orig]) == 1)

        self._check_repo_state(repo, None, [], tags=[])
