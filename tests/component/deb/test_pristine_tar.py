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

from tests.component import ComponentTestBase
from tests.component.deb.fixtures import RepoFixtures
from tests.component.deb import DEB_TEST_DATA_DIR

from gbp.scripts.pristine_tar import main as pristine_tar


def _dsc_file(pkg, version, dir='dsc-3.0'):
    return os.path.join(DEB_TEST_DATA_DIR, dir, '%s_%s.dsc' % (pkg, version))


DEFAULT_DSC = _dsc_file('hello-debhelper', '2.6-2')


class TestPristineTar(ComponentTestBase):
    """Test pristine-tar commit tool"""
    pkg = "hello-debhelper"
    def_branches = ['master', 'upstream', 'pristine-tar']

    def _orig(self, version, dir='dsc-3.0'):
        return os.path.join(DEB_TEST_DATA_DIR,
                            dir,
                            '%s_%s.orig.tar.gz' % (self.pkg, version))

    @RepoFixtures.quilt30(DEFAULT_DSC, opts=['--no-pristine-tar'])
    def test_run(self, repo):
        """
        Test that adding pristine-tar commit works
        """
        orig = self._orig("2.6")
        assert pristine_tar(["arg0", "commit", orig]) == 0
        self._check_repo_state(repo, "master", ["master", "upstream", "pristine-tar"])

    @RepoFixtures.quilt30(DEFAULT_DSC, opts=['--no-pristine-tar'])
    def test_missing_upstream_signature(self, repo):
        """
        Test that adding pristine-tar commit works
        """
        orig = self._orig("2.6")
        assert pristine_tar(["arg0", "--upstream-signature=on", "commit", orig]) == 1
        self._check_log(-1, ".*/hello-debhelper_2.6.orig.tar.gz does not have a signature file")

    @RepoFixtures.quilt30(DEFAULT_DSC, opts=['--no-pristine-tar'])
    def test_upstream_signature(self, repo):
        """
        Test that adding pristine-tar commit works
        """
        orig = self._orig("2.8")
        assert pristine_tar(["arg0", "--upstream-signature=on", "commit", orig]) == 0
        self._check_repo_state(repo, "master", ["master", "upstream", "pristine-tar"])
        assert repo.ls_tree("pristine-tar") == {
            b"hello-debhelper_2.8.orig.tar.gz.id",
            b"hello-debhelper_2.8.orig.tar.gz.delta",
            b"hello-debhelper_2.8.orig.tar.gz.asc",
        }

    @RepoFixtures.quilt30(_dsc_file('hello-debhelper',
                                    '2.8-1',
                                    dir='dsc-3.0-additional-tarballs'),
                          opts=['--no-pristine-tar'])
    def test_run_component_tarball(self, repo):
        """
        Test that adding pristine-tar commits with additional tarballs works
        """
        orig = self._orig("2.8", dir="dsc-3.0-additional-tarballs")
        assert pristine_tar(["arg0", "commit", "--component=foo", orig]) == 0
        self._check_repo_state(repo, "master", ["master", "upstream", "pristine-tar"])

        ptars = [('hello-debhelper_2.8.orig.tar.gz', 'pristine-tar'),
                 ('hello-debhelper_2.8.orig-foo.tar.gz', 'pristine-tar^')]
        for f, w in ptars:
            assert repo.get_subject(w) == "pristine-tar data for %s" % f
