# vim: set fileencoding=utf-8 :
"""Test L{gbp.deb.rollbackgit}"""

import os

from . testutils import DebianGitTestRepo
from gbp.deb.rollbackgit import RollbackDebianGitRepository
from gbp.git.repository import GitRepositoryError


class TestRollbackGitRepository(DebianGitTestRepo):

    def setUp(self):
        DebianGitTestRepo.setUp(self, RollbackDebianGitRepository)

    def test_empty_rollback(self):
        self.repo.rollback()
        self.assertEqual(self.repo.rollback_errors, [])

    def test_rrr_tag(self):
        self.repo.rrr_tag('doesnotexist')
        self.assertEqual(self.repo.rollbacks, [('doesnotexist', 'tag', 'delete', None)])
        self.repo.rollback()
        self.assertEqual(self.repo.rollback_errors, [])

    def test_rrr_branch(self):
        self.repo.rrr_branch('doesnotexist', 'delete')
        self.assertEqual(self.repo.rollbacks, [('doesnotexist', 'branch', 'delete', None)])
        self.repo.rollback()
        self.assertEqual(self.repo.rollback_errors, [])

    def test_rrr_merge(self):
        self.repo.rrr_merge('HEAD')
        self.assertEqual(self.repo.rollbacks, [('HEAD', 'commit', 'abortmerge', None)])
        self.repo.rollback()
        self.assertEqual(self.repo.rollback_errors, [])

    def test_rrr_merge_abort(self):
        self.repo.rrr_merge('HEAD')
        self.assertEqual(self.repo.rollbacks, [('HEAD', 'commit', 'abortmerge', None)])
        # Test that we abort the merge in case MERGE_HEAD exists
        with open(os.path.join(self.repo.git_dir, 'MERGE_HEAD'), 'w'):
            pass
        self.assertTrue(self.repo.is_in_merge())
        self.repo.rollback()
        self.assertFalse(self.repo.is_in_merge())
        self.assertEqual(self.repo.rollback_errors, [])

    def test_rrr_unknown_action(self):
        with self.assertRaisesRegex(GitRepositoryError, "Unknown action 'unknown' for tag 'doesnotmatter'"):
            self.repo.rrr('doesnotmatter', 'unknown', 'tag')
