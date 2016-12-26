# vim: set fileencoding=utf-8 :
"""Test L{gbp.command_wrappers.Command}'s tarball unpack"""

import os
import unittest

from gbp.scripts.import_orig import (ImportOrigDebianGitRepository, GbpError)
from gbp.scripts.common.import_orig import download_orig
from . testutils import DebianGitTestRepo


class TestImportOrigGitRepository(DebianGitTestRepo):

    def setUp(self):
        DebianGitTestRepo.setUp(self, ImportOrigDebianGitRepository)

    def test_empty_rollback(self):
        self.repo.rollback()
        self.assertEquals(self.repo.rollback_errors, [])

    def test_rrr_delete_tag(self):
        self.repo.rrr('doesnotmatter', 'delete', 'tag')
        self.assertEquals(self.repo.rollbacks, [('doesnotmatter', 'tag', 'delete', None)])
        self.repo.rollback()
        self.assertEquals(self.repo.rollback_errors, [])

    def test_rrr_delete_branch(self):
        self.repo.rrr('doesnotmatter', 'delete', 'branch')
        self.assertEquals(self.repo.rollbacks, [('doesnotmatter', 'branch', 'delete', None)])
        self.repo.rollback()
        self.assertEquals(self.repo.rollback_errors, [])

    def test_rrr_unknown_action(self):
        with self.assertRaisesRegexp(GbpError, "Unknown action unknown for tag doesnotmatter"):
            self.repo.rrr('doesnotmatter', 'unknown', 'tag')


@unittest.skipUnless(os.getenv("GBP_NETWORK_TESTS"), "network tests disabled")
class TestImportOrigDownload(DebianGitTestRepo):
    HOST = 'git.sigxcpu.org'

    def setUp(self):
        DebianGitTestRepo.setUp(self, ImportOrigDebianGitRepository)
        os.chdir(self.repodir)

    def test_404_download(self):
        with self.assertRaisesRegexp(GbpError, "404 Client Error: Not Found for url"):
            download_orig("https://{host}/does_not_exist".format(host=self.HOST))

    def test_200_download(self):
        pkg = 'hello-debhelper_2.6.orig.tar.gz'
        url = "https://{host}/cgit/gbp/deb-testdata/tree/dsc-3.0/{pkg}".format(host=self.HOST,
                                                                               pkg=pkg)
        self.assertEqual(download_orig(url).path, '../%s' % pkg)
