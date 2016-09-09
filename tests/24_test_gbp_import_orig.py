# vim: set fileencoding=utf-8 :
"""Test L{gbp.command_wrappers.Command}'s tarball unpack"""

from gbp.scripts.import_orig import (ImportOrigDebianGitRepository, GbpError)
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
