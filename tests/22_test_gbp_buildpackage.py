# vim: set fileencoding=utf-8 :
"""Test L{gbp.command_wrappers.Command}'s tarball unpack"""

from gbp.scripts.buildpackage import (get_pbuilder_dist,
                                      setup_pbuilder,
                                      GbpError)
from . testutils import DebianGitTestRepo

from mock import patch


class TestGbpBuildpackageDep14(DebianGitTestRepo):
    class Options(object):
        pass

    def setUp(self):
        DebianGitTestRepo.setUp(self)
        self.add_file('doesnotmatter')
        self.options = self.Options()
        self.options.pbuilder_dist = 'DEP14'

    @patch('gbp.deb.get_vendor', return_value='Debian')
    def test_get_pbuilder_dist_no_dep14(self, patch):
        self.options.pbuilder_dist = 'notdep14'
        self.assertEqual(get_pbuilder_dist(self.options, self.repo),
                         self.options.pbuilder_dist)

    @patch('gbp.deb.get_vendor', return_value='Debian')
    def test_get_pbuilder_dist_dep14_debian_sid(self, patch):
        branch = 'debian/sid'
        self.repo.create_branch(branch)
        self.repo.set_branch(branch)
        self.assertEqual(get_pbuilder_dist(self.options, self.repo), '')
        patch.assert_called_once_with()

    @patch('gbp.deb.get_vendor', return_value='Debian')
    def test_get_pbuilder_dist_dep14_debian_master(self, patch):
        branch = 'debian/master'
        self.repo.create_branch(branch)
        self.repo.set_branch(branch)
        self.assertEqual(get_pbuilder_dist(self.options, self.repo), '')
        patch.assert_called_once_with()

    @patch('gbp.deb.get_vendor', return_value='Debian')
    def test_get_pbuilder_dist_dep14_debian_suite(self, patch):
        branch = 'debian/squeeze-lts'
        self.repo.create_branch(branch)
        self.repo.set_branch(branch)
        self.assertEqual(get_pbuilder_dist(self.options, self.repo), 'squeeze-lts')
        patch.assert_called_once_with()

    @patch('gbp.deb.get_vendor', return_value='Debian')
    def test_get_pbuilder_dist_dep14_debian_native(self, patch):
        self.assertEqual(get_pbuilder_dist(self.options, self.repo, True), '')

    @patch('gbp.deb.get_vendor', return_value='Debian')
    def test_get_pbuilder_dist_dep14_vendor_sid(self, patch):
        branch = 'downstream/sid'
        self.repo.create_branch(branch)
        self.repo.set_branch(branch)
        self.assertEqual(get_pbuilder_dist(self.options, self.repo), 'downstream_sid')
        patch.assert_called_once_with()

    @patch('gbp.deb.get_vendor', return_value='Debian')
    def test_get_pbuilder_dist_dep14_vendor_suite(self, patch):
        branch = 'downstream/mies-lts'
        self.repo.create_branch(branch)
        self.repo.set_branch(branch)
        self.assertEqual(get_pbuilder_dist(self.options, self.repo), 'downstream_mies-lts')

    @patch('gbp.deb.get_vendor', return_value='Debian')
    def test_get_pbuilder_dist_dep14_no_vendor(self, patch):
        branch = 'sid'
        self.repo.create_branch(branch)
        self.repo.set_branch(branch)
        with self.assertRaisesRegexp(GbpError,
                                     "DEP14 DIST: Current branch 'sid' does not match vendor/suite"):
            get_pbuilder_dist(self.options, self.repo)

    def test_get_pbuilder_dist_dep14_too_many_slashes(self):
        branch = 'too/many/slashes'
        self.repo.create_branch(branch)
        self.repo.set_branch(branch)
        with self.assertRaisesRegexp(GbpError,
                                     "DEP14 DIST: Current branch 'too/many/slashes' does not match vendor/suite"):
            get_pbuilder_dist(self.options, self.repo)


class TestGbpBuildpackageSetupPbuilder(DebianGitTestRepo):
    class Options(object):
        use_pbuilder = True
        pbuilder_dist = 'sid'
        pbuilder_arch = ''
        use_qemubuilder = False
        pbuilder_autoconf = True
        pbuilder_options = ''

    def setUp(self):
        DebianGitTestRepo.setUp(self)
        self.options = self.Options()

    def test_setup_pbuilder(self):
        self.assertEqual(setup_pbuilder(self.options,
                                        self.repo,
                                        True),
                         ({'GBP_PBUILDER_DIST': 'sid', 'DIST': 'sid'},
                          {'GBP_PBUILDER_DIST': 'sid'}))

    def test_setup_pbuilder_arch(self):
        self.options.pbuilder_arch = 'arm64'
        self.assertEqual(setup_pbuilder(self.options,
                                        self.repo,
                                        True),
                         ({'ARCH': 'arm64',
                           'DIST': 'sid',
                           'GBP_PBUILDER_ARCH': 'arm64',
                           'GBP_PBUILDER_DIST': 'sid'},
                          {'GBP_PBUILDER_ARCH': 'arm64',
                           'GBP_PBUILDER_DIST': 'sid'}))
