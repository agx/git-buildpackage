# vim: set fileencoding=utf-8 :

"""Test  L{GitRepository}'s write_tree method"""

from __future__ import print_function

from . import context  # noqa: 401
from . import testutils

import os

import gbp.log
import gbp.git
import gbp.errors


class TestWriteTree(testutils.DebianGitTestRepo):
    def _write_testtree(self):
        """Write a test tree"""
        paths = []
        for i in range(4):
            path = os.path.join(self.repo.path, 'testfile%d' % i)
            with open(path, 'w') as f:
                print("testdata %d" % i, file=f)
            paths.append(path)
        return paths

    def test_write_tree_index_nonexistent(self):
        """Write out index file to non-existent dir"""
        paths = self._write_testtree()
        self.repo.add_files(paths)
        self.assertRaises(gbp.git.GitRepositoryError,
                          self.repo.write_tree,
                          '/does/not/exist')

    def test_write_tree(self):
        """Write out index file to alternate index file"""
        index = os.path.join(self.repo.git_dir, 'gbp_index')
        expected_sha1 = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'

        paths = self._write_testtree()
        self.repo.add_files(paths)
        sha1 = self.repo.write_tree(index)
        self.assertTrue(os.path.exists(index))
        self.assertEqual(sha1, expected_sha1)
        self.assertTrue(self.repo.has_treeish(expected_sha1))

    def test_commit_tree(self):
        """Commit a tree"""
        expected_sha1 = 'ea63fcee40675a5f82ea6bedbf29ca86d89c5f63'
        paths = self._write_testtree()
        self.repo.add_files(paths)
        sha1 = self.repo.write_tree()
        self.assertEqual(sha1, expected_sha1)
        self.assertTrue(self.repo.has_treeish(expected_sha1))
        commit = self.repo.commit_tree(sha1, "first commit", parents=[],
                                       committer=dict(name='foo',
                                                      email='foo@example.com'),
                                       author=dict(name='bar',
                                                   email='bar@example.com'),
                                       )
        self.assertEqual(len(commit), 40)
        # commit the same tree again using the previous commit as parent
        self.repo.commit_tree(sha1, "second commit", parents=[commit])
        # commit the same tree again using a non-existent parent
        self.assertRaises(gbp.errors.GbpError,
                          self.repo.commit_tree,
                          sha1,
                          "failed commit",
                          ['doesnotexist'])

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
