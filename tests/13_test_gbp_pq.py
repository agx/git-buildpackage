# vim: set fileencoding=utf-8 :
# (C) 2012,2015 Guido Günther <agx@sigxcpu.org>
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
"""Test L{gbp.pq}"""

from . import context
from . import testutils

import os
import unittest

from gbp.command_wrappers import GitCommand
from gbp.scripts.pq import (generate_patches, export_patches,
                            import_quilt_patches, rebase_pq,
                            switch_pq,
                            SERIES_FILE)
import gbp.scripts.common.pq as pq
import gbp.patch_series


class TestPqOptions(object):
    abbrev = 7
    drop = False
    patch_num_format = '%04d-'
    patch_numbers = False
    renumber = False


class TestApplyAndCommit(testutils.DebianGitTestRepo):
    """Test L{gbp.pq}'s apply_and_commit"""

    def setUp(self):
        testutils.DebianGitTestRepo.setUp(self)
        self.add_file('bar')

    def test_apply_and_commit_patch(self):
        """Test applying a single patch"""
        patch = gbp.patch_series.Patch(_patch_path('foo.patch'))

        pq.apply_and_commit_patch(self.repo, patch, None)
        self.assertIn(b'foo', self.repo.list_files())

    def test_apply_and_commit_patch_preserve_subject(self):
        """Test applying a patch preserves the subject"""
        patch = gbp.patch_series.Patch(_patch_path('brackets-in-subject.patch'))

        pq.apply_and_commit_patch(self.repo, patch, None)
        self.assertIn(b'foo', self.repo.list_files())
        info = self.repo.get_commit_info('HEAD')
        self.assertEquals('[text] foobar', info['subject'])

    def test_topic(self):
        """Test if setting a topic works"""
        patch = gbp.patch_series.Patch(_patch_path('foo.patch'))

        pq.apply_and_commit_patch(self.repo, patch, None, topic='foobar')
        info = self.repo.get_commit_info('HEAD')
        self.assertIn('Gbp-Pq: Topic foobar', info['body'])

    def test_name(self):
        """Test if setting a name works"""
        patch = gbp.patch_series.Patch(_patch_path('foo.patch'))

        pq.apply_and_commit_patch(self.repo, patch, None, name='foobar')
        info = self.repo.get_commit_info('HEAD')
        self.assertIn('Gbp-Pq: Name foobar', info['body'])

    @testutils.skip_without_cmd('dpkg')
    def test_debian_missing_author(self):
        """
        Check if we parse the author from debian control if it's missing in the patch.
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
                      "Maintainer: Guido Günther <gg@godiug.net>".encode('utf-8'),
                      mode='wb+')

        maintainer = pq.get_maintainer_from_control(self.repo)
        orig_warn = gbp.log.warn
        gbp.log.warn = _check_log
        pq.apply_and_commit_patch(self.repo, patch, maintainer)
        gbp.log.warn = orig_warn
        info = self.repo.get_commit_info('HEAD')
        self.assertEqual(info['author'].email, 'gg@godiug.net')
        self.assertIn(b'foo', self.repo.list_files())


class TestApplySinglePatch(testutils.DebianGitTestRepo):
    """Test L{gbp.pq}'s apply_single_patch"""

    def setUp(self):
        testutils.DebianGitTestRepo.setUp(self)
        self.add_file('bar')

    def test_apply_single_patch(self):
        """Test applying a single patch"""

        patch = gbp.patch_series.Patch(_patch_path('foo.patch'))

        self.repo.create_branch(pq.pq_branch_name('master'))
        pq.apply_single_patch(self.repo, 'master', patch, None)
        self.assertIn(b'foo', self.repo.list_files())


class TestWritePatch(testutils.DebianGitTestRepo):
    """Test L{gbp.pq}'s write_patch """

    def setUp(self):
        testutils.DebianGitTestRepo.setUp(self)
        self.add_file('bar', 'bar')

    def tearDown(self):
        context.teardown()

    def _test_generate_patches(self, changes, expected_patches, opts):
        self.assertEqual(len(changes), len(expected_patches))

        d = context.new_tmpdir(__name__)
        expected_paths = [os.path.join(str(d), n) for n in expected_patches]

        # Commit changes
        for c in changes:
            self.add_file(c[0], c[1], c[2])

        # Write it out as patch and check its existence
        origin = 'HEAD~%d' % len(changes)
        patchfiles = generate_patches(self.repo, origin, 'HEAD', str(d), opts)
        for expected in expected_paths:
            self.assertIn(expected, patchfiles)
            self.assertTrue(os.path.exists(expected))

        # Reapply the patch to a new branch
        self.repo.create_branch('testapply', origin)
        self.repo.set_branch('testapply')
        for expected in expected_paths:
            self.repo.apply_patch(expected)
        self.repo.commit_all("foo")
        diff = self.repo.diff('master', 'testapply')
        # Branches must be identical afterwards
        self.assertEqual(b'', diff)

    def test_generate_patches(self):
        """Test generation of patches"""

        expected_patches = ['gbptest/added-foo.patch',
                            'gbptest/patchname.diff']

        changes = [('foo', 'foo', ("added foo\n\n"
                                   "Gbp-Pq: Topic gbptest")),
                   ('baz', 'baz', ("added bar\n\n"
                                   "Gbp-Pq: Topic gbptest\n"
                                   "Gbp-Pq: Name patchname.diff"))]

        opts = TestPqOptions()
        opts.patch_num_format = '%04d-'
        self._test_generate_patches(changes, expected_patches, opts)

    def test_generate_renumbered_patches(self):
        """Test generation of renumbered patches"""

        expected_patches = ['gbptest/01_added-foo.patch',
                            'gbptest/02_patchname.diff']

        changes = [('foo', 'foo', ("added foo\n\n"
                                   "Gbp-Pq: Topic gbptest")),
                   ('baz', 'baz', ("added bar\n\n"
                                   "Gbp-Pq: Topic gbptest\n"
                                   "Gbp-Pq: Name 099-patchname.diff"))]

        opts = TestPqOptions()
        opts.patch_num_format = '%02d_'
        opts.renumber = True
        opts.patch_numbers = True
        self._test_generate_patches(changes, expected_patches, opts)

    def test_generate_patches_with_name_clashes(self):
        """Test generation of patches which have name clashes"""

        expected_patches = ['gbptest/added-foo.patch',
                            'gbptest/patchname.diff',
                            'gbptest/patchname-1.diff',
                            'gbptest/patchname-2.diff']

        changes = [('foo', 'foo', ("added foo\n\n"
                                   "Gbp-Pq: Topic gbptest")),
                   ('baz', 'baz', ("added bar\n\n"
                                   "Gbp-Pq: Topic gbptest\n"
                                   "Gbp-Pq: Name 099-patchname.diff")),
                   ('qux', 'qux', ("added qux\n\n"
                                   "Gbp-Pq: Topic gbptest\n"
                                   "Gbp-Pq: Name 100-patchname.diff")),
                   ('norf', 'norf', ("added norf\n\n"
                                     "Gbp-Pq: Topic gbptest\n"
                                     "Gbp-Pq: Name 101-patchname.diff"))]

        opts = TestPqOptions()
        opts.renumber = True
        opts.patch_num_format = '%02d_'
        self._test_generate_patches(changes, expected_patches, opts)


class TestExport(testutils.DebianGitTestRepo):
    class Options(TestPqOptions):
        commit = False
        meta_closes = False
        meta_closes_bugnum = ''
        pq_from = 'DEBIAN'

    def setUp(self):
        testutils.DebianGitTestRepo.setUp(self)
        self.add_file('bar', 'bar')

    def test_drop(self):
        """Test if we drop the patch-queue branch with --drop"""
        repo = self.repo
        start = repo.get_branch()
        pq_branch = os.path.join('patch-queue', start)
        opts = TestExport.Options()
        opts.drop = True

        repo.create_branch(pq.pq_branch_name('master'))
        switch_pq(repo, start, opts)
        self.assertEqual(repo.get_branch(), pq_branch)
        export_patches(repo, pq_branch, opts)
        self.assertEqual(repo.get_branch(), start)
        self.assertFalse(repo.has_branch(pq_branch))

    def test_commit(self):
        """Test if we commit the patch-queue branch with --commit"""
        repo = self.repo
        start = repo.get_branch()
        pq_branch = os.path.join('patch-queue', start)
        opts = TestExport.Options()
        opts.commit = True
        repo.create_branch(pq.pq_branch_name('master'))
        switch_pq(repo, start, opts)
        self.assertEqual(len(repo.get_commits()), 1)
        self.assertEqual(repo.get_branch(), pq_branch)
        self.add_file('foo', 'foo')
        export_patches(repo, pq_branch, opts)
        self.assertEqual(repo.get_branch(), start)
        self.assertTrue(repo.has_branch(pq_branch))
        self.assertEqual(len(repo.get_commits()), 2,
                         "Export did not create commit")
        export_patches(repo, pq_branch, opts)
        self.assertEqual(repo.get_branch(), start)
        self.assertEqual(len(repo.get_commits()), 2,
                         "Export must not create another commit")

    def test_commit_dropped_patches(self):
        """Test if we commit the patch-queue branch with all patches dropped"""
        repo = self.repo
        start = repo.get_branch()
        pq_branch = os.path.join('patch-queue', start)
        opts = TestExport.Options()
        opts.commit = True
        patch_dir = os.path.join(repo.path, 'debian/patches')
        os.makedirs(patch_dir)
        with open(os.path.join(patch_dir, 'series'), 'w') as f:
            f.write("patch1.diff\n")
            f.write("patch2.diff\n")
        repo.add_files('debian/patches')
        repo.commit_all('Add series file')
        repo.create_branch(pq.pq_branch_name('master'))
        switch_pq(repo, start, opts)
        self.assertEqual(len(repo.get_commits()), 2)
        self.assertEqual(repo.get_branch(), pq_branch)
        export_patches(repo, pq_branch, opts)
        self.assertEqual(repo.get_branch(), start)
        self.assertTrue(repo.has_branch(pq_branch))
        self.assertEqual(len(repo.get_commits()), 3,
                         "Export did not create commit")
        self.assertIn(b"Drop patch1.diff:", repo.show('HEAD'))
        self.assertIn(b"Drop patch2.diff:", repo.show('HEAD'))


class TestParseGbpCommand(unittest.TestCase):
    def test_empty_body(self):
        """Test command filtering with an empty body"""
        info = {'body': ''}
        (cmds, body) = pq.parse_gbp_commands(info, ['tag'], ['cmd1'], ['cmd2'])
        self.assertEquals(cmds, {})
        self.assertEquals(body, '')

    def test_noarg_cmd(self):
        orig_body = '\n'.join(["Foo",
                               "tag: cmd1"])
        info = {'body': orig_body}
        (cmds, body) = pq.parse_gbp_commands(info, 'tag', ['cmd'], ['argcmd'])
        self.assertEquals(cmds, {'cmd': None})
        self.assertEquals(body, orig_body)

    def test_filter_cmd(self):
        orig_body = '\n'.join(["Foo",
                               "tag: cmd1"])
        info = {'body': orig_body}
        (cmds, body) = pq.parse_gbp_commands(info, 'tag', ['cmd'], ['argcmd'], ['cmd'])
        self.assertEquals(cmds, {'cmd': None})
        self.assertEquals(body, 'Foo')


class TestFromTAG(testutils.DebianGitTestRepo):
    """Test L{gbp.pq}'s pq-from=TAG"""

    class Options(TestPqOptions):
        commit = True
        force = False
        meta_closes = 'Closes|LP'
        meta_closes_bugnum = r'(?:bug|issue)?\#?\s?\d+'
        pq_from = 'TAG'
        upstream_tag = 'upstream/%(version)s'

    def git_create_empty_branch(self, branch):
        GitCommand('checkout', cwd=self.repo.path)(['-q', '--orphan', branch])
        GitCommand('rm', cwd=self.repo.path)(['-rf', '.'])

    def setUp(self):
        testutils.DebianGitTestRepo.setUp(self)
        self.add_file('debian/control')
        self.add_file(
            'debian/changelog',
            'foo (0.0.1-1) UNRELEASED; urgency=medium\n'
            '\n'
            '  * Initial foo\n'
            '\n'
            ' -- Mr. T. S. <t@example.com>  '
            'Thu, 01 Jan 1970 00:00:00 +0000\n'
        )
        self.git_create_empty_branch('bar')
        self.add_file('foo', 'foo')
        self.repo.create_tag('upstream/0.0.1')
        self.repo.set_branch('master')

    def test_empty(self):

        import_quilt_patches(self.repo,
                             branch=self.repo.get_branch(),
                             series=SERIES_FILE,
                             tries=1,
                             force=TestFromTAG.Options.force,
                             pq_from=TestFromTAG.Options.pq_from,
                             upstream_tag=TestFromTAG.Options.upstream_tag)
        diff = self.repo.diff(self.repo.get_branch(), 'upstream/0.0.1')
        self.assertEqual(b'', diff)
        diff = self.repo.diff(self.repo.get_branch(), 'master')
        self.assertNotEqual(b'', diff)

        rebase_pq(self.repo,
                  branch=self.repo.get_branch(),
                  options=TestFromTAG.Options)
        diff = self.repo.diff(self.repo.get_branch(), 'upstream/0.0.1')
        self.assertEqual(b'', diff)
        diff = self.repo.diff(self.repo.get_branch(), 'master')
        self.assertNotEqual(b'', diff)

        export_patches(self.repo,
                       branch=self.repo.get_branch(),
                       options=TestFromTAG.Options())
        diff = self.repo.diff(self.repo.get_branch(), self.repo.head)
        self.assertEqual(b'', diff)

    def test_adding_patch(self):
        import_quilt_patches(self.repo,
                             branch=self.repo.get_branch(),
                             series=SERIES_FILE,
                             tries=1,
                             force=TestFromTAG.Options.force,
                             pq_from=TestFromTAG.Options.pq_from,
                             upstream_tag=TestFromTAG.Options.upstream_tag)
        self.add_file('bar', 'bar', 'added bar')
        export_patches(self.repo,
                       branch=self.repo.get_branch(),
                       options=TestFromTAG.Options())
        self.assertTrue(os.path.exists(os.path.join(self.repo.path,
                                                    os.path.dirname(SERIES_FILE),
                                                    'added-bar.patch')))
        switch_pq(self.repo, 'master', TestFromTAG.Options)
        rebase_pq(self.repo,
                  branch=self.repo.get_branch(),
                  options=TestFromTAG.Options())
        export_patches(self.repo,
                       branch=self.repo.get_branch(),
                       options=TestFromTAG.Options())
        self.assertTrue(os.path.exists(os.path.join(self.repo.path,
                                                    os.path.dirname(SERIES_FILE),
                                                    'added-bar.patch')))
        # New upstream release
        self.repo.set_branch('bar')
        GitCommand('cherry-pick', cwd=self.repo.path)(['patch-queue/master'])
        self.repo.create_tag('upstream/0.0.2')
        self.repo.set_branch('master')
        self.add_file(
            'debian/changelog',
            'foo (0.0.2-1) UNRELEASED; urgency=medium\n'
            '\n'
            '  * Initial foo\n'
            '\n'
            ' -- Mr. T. S. <t@example.com>  '
            'Thu, 01 Jan 1970 00:00:00 +0000\n'
        )
        switch_pq(self.repo, 'master', TestFromTAG.Options())
        rebase_pq(self.repo,
                  branch=self.repo.get_branch(),
                  options=TestFromTAG.Options())
        export_patches(self.repo,
                       branch=self.repo.get_branch(),
                       options=TestFromTAG.Options())
        self.assertFalse(os.path.exists(os.path.join(self.repo.path,
                                                     os.path.dirname(SERIES_FILE),
                                                     'added-bar.patch')))


def _patch_path(name):
    return os.path.join(context.projectdir, 'tests/data', name)
