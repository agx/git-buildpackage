# vim: set fileencoding=utf-8 :

import os

from . testutils import DebianGitTestRepo
from gbp.git.repository import GitRepositoryError


class TestGitRepositoryCommitDir(DebianGitTestRepo):
    def setUp(self):
        DebianGitTestRepo.setUp(self)
        self.content = os.path.join(str(self.tmpdir), 'new')
        os.mkdir(self.content)
        with open(os.path.join(self.content, 'file1'), 'w') as f:
            f.write('content1')

    def test_simple(self):
        self.repo.commit_dir(self.content,
                             'new content',
                             'master',
                             create_missing_branch=True)
        self.assertEquals(self.repo.show('master:file1'), 'content1')

    def test_long_reflog(self):
        """Make sure we fail on onverly long msg resulting in an
        overly long reflog enry"""
        with self.assertRaises(GitRepositoryError):
            self.repo.commit_dir(self.content,
                                 'foo' * 100000,
                                 'master',
                                 create_missing_branch=True)

    def test_long_msg_854333(self):
        """Make sure we shorten the reflog entry properly"""
        self.repo.commit_dir(self.content,
                             'foo\n' * 100000,
                             'master',
                             create_missing_branch=True)
        self.assertEquals(self.repo.show('master:file1'), 'content1')
        out, dummy, ret = self.repo._git_inout('reflog', [])
        self.assertEquals(ret, 0)
        self.assertIn('HEAD@{0}: gbp: foo\n', out)
