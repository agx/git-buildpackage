# vim: set fileencoding=utf-8 :

"""Test L{gbp.pq}"""

import os
import unittest

import gbp.scripts.common.pq
import gbp.patch_series
import tests.testutils as testutils

class TestApplyAndCommit(testutils.DebianGitTestRepo):
    """Test L{gbp.pq}'s apply_and_commit"""

    def setUp(self):
        testutils.DebianGitTestRepo.setUp(self)
        self.add_file('bar')

    def test_apply_and_commit_patch(self):
        """Test applying a single patch"""
        patch = gbp.patch_series.Patch(
            os.path.join(os.path.abspath(os.path.curdir),
                         'tests/data/foo.patch'))

        gbp.scripts.common.pq.apply_and_commit_patch(self.repo, patch, None)
        self.assertIn('foo', self.repo.list_files())


    def test_topic(self):
        """Test if setting a topic works"""
        patch = gbp.patch_series.Patch(
            os.path.join(os.path.abspath(os.path.curdir),
                         'tests/data/foo.patch'))

        gbp.scripts.common.pq.apply_and_commit_patch(self.repo, patch, None,
                                                     topic='foobar')
        info = self.repo.get_commit_info('HEAD')
        self.assertIn('Gbp-Pq-Topic: foobar', info['body'])

    @unittest.skipIf(not os.path.exists('/usr/bin/dpkg'), 'Dpkg not found')
    def test_debian_missing_author(self):
        """
        Check if we parse the author from debian control
        if it's missing.
        """
        patch = gbp.patch_series.Patch(
            os.path.join(os.path.abspath(os.path.curdir),
                         'tests/data/foo.patch'))

        # Overwrite data parsed from patch:
        patch.author
        patch.info['author'] = None
        patch.info['email'] = None

        # Fake a control file
        self.add_file("debian/control",
                      "Maintainer: Guido Günther <gg@godiug.net>")

        c = gbp.scripts.common.pq.get_maintainer_from_control
        gbp.scripts.common.pq.apply_and_commit_patch(self.repo,
                                                     patch,
                                                     c)
        info = self.repo.get_commit_info('HEAD')
        self.assertEqual(info['author'].email, 'gg@godiug.net')
        self.assertIn('foo', self.repo.list_files())

class TestApplySinglePatch(testutils.DebianGitTestRepo):
    """Test L{gbp.pq}'s """

    def setUp(self):
        testutils.DebianGitTestRepo.setUp(self)
        self.add_file('bar')

    def test_apply_single_patch(self):
        """Test applying a single patch"""
        patch = gbp.patch_series.Patch(
            os.path.join(os.path.abspath(os.path.curdir),
                         'tests/data/foo.patch'))

        gbp.scripts.common.pq.apply_single_patch(self.repo, 'master', patch,
                                                 None)
        self.assertIn('foo', self.repo.list_files())






