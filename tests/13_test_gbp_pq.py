# vim: set fileencoding=utf-8 :
# (C) 2012 Guido Günther <agx@sigxcpu.org>
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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Test L{gbp.pq}"""

from . import context

import os
import logging
import unittest

from gbp.scripts.pq import generate_patches
import gbp.scripts.common.pq as pq
import gbp.patch_series
import tests.testutils as testutils

class TestApplyAndCommit(testutils.DebianGitTestRepo):
    """Test L{gbp.pq}'s apply_and_commit"""

    def setUp(self):
        testutils.DebianGitTestRepo.setUp(self)
        self.add_file('bar')

    def test_apply_and_commit_patch(self):
        """Test applying a single patch"""
        patch = gbp.patch_series.Patch(_patch_path('foo.patch'))

        pq.apply_and_commit_patch(self.repo, patch, None)
        self.assertIn('foo', self.repo.list_files())


    def test_topic(self):
        """Test if setting a topic works"""
        patch = gbp.patch_series.Patch(_patch_path('foo.patch'))

        pq.apply_and_commit_patch(self.repo, patch, None, topic='foobar')
        info = self.repo.get_commit_info('HEAD')
        self.assertIn('Gbp-Pq-Topic: foobar', info['body'])

    @unittest.skipIf(not os.path.exists('/usr/bin/dpkg'), 'Dpkg not found')
    def test_debian_missing_author(self):
        """
        Check if we parse the author from debian control
        if it's missing in the patch.
        """
        def _check_log(msg):
            self.assertEqual(msg, "Patch 'foo.patch' has no authorship "
                         "information, using 'Guido Günther <gg@godiug.net>'")

        patch = gbp.patch_series.Patch(_patch_path('foo.patch'))

        # Overwrite data parsed from patch:
        patch.author
        patch.info['author'] = None
        patch.info['email'] = None

        # Fake a control file
        self.add_file("debian/control",
                      "Maintainer: Guido Günther <gg@godiug.net>")

        maintainer = pq.get_maintainer_from_control(self.repo)
        orig_warn = gbp.log.warn
        gbp.log.warn = _check_log
        pq.apply_and_commit_patch(self.repo, patch, maintainer)
        gbp.log.warn = orig_warn
        info = self.repo.get_commit_info('HEAD')
        self.assertEqual(info['author'].email, 'gg@godiug.net')
        self.assertIn('foo', self.repo.list_files())

class TestApplySinglePatch(testutils.DebianGitTestRepo):
    """Test L{gbp.pq}'s apply_single_patch"""

    def setUp(self):
        testutils.DebianGitTestRepo.setUp(self)
        self.add_file('bar')

    def test_apply_single_patch(self):
        """Test applying a single patch"""

        patch = gbp.patch_series.Patch(_patch_path('foo.patch'))

        pq.apply_single_patch(self.repo, 'master', patch, None)
        self.assertIn('foo', self.repo.list_files())

class TestWritePatch(testutils.DebianGitTestRepo):
    """Test L{gbp.pq}'s write_patch """

    def setUp(self):
        testutils.DebianGitTestRepo.setUp(self)
        self.add_file('bar', 'bar')

    def tearDown(self):
        context.teardown()

    def test_generate_patches(self):
        """Test generation of patches"""

        class opts: patch_numbers = False

        # Add test file with topic:
        msg = ("added foo\n\n"
               "Gbp-Pq-Topic: gbptest")
        self.add_file('foo', 'foo', msg)

        # Write it out as patch and check it's existence
        d = context.new_tmpdir(__name__)
        patchfile = generate_patches(self.repo, 'HEAD^', 'HEAD', str(d),
                                     opts)[0]
        expected = os.path.join(str(d), 'gbptest', 'added-foo.patch')

        self.assertTrue(os.path.exists(expected))
        logging.debug(file(expected).read())

        # Reapply the patch to a new branch
        self.repo.create_branch('testapply', 'HEAD^')
        self.repo.set_branch('testapply')
        self.repo.apply_patch(expected)
        self.repo.commit_all("foo")
        diff = self.repo.diff('master', 'testapply')
        # Branches must be identical afterwards
        self.assertEqual('', diff)

def _patch_path(name):
    return os.path.join(context.projectdir, 'tests/data', name)
