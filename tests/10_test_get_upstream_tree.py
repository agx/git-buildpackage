# vim: set fileencoding=utf-8 :

"""Test  L{export_orig}'s git_archive_get_upstream_tree method"""

from . import context  # noqa: F401
from . import testutils

import gbp.errors
import gbp.scripts.export_orig as export_orig


class MockOptions(object):
    def __init__(self,
                 upstream_branch=None,
                 upstream_tree=None,
                 upstream_tag=None):
        self.upstream_branch = upstream_branch
        self.upstream_tree = upstream_tree
        self.upstream_tag = upstream_tag


class TestGetUpstreamTree(testutils.DebianGitTestRepo):
    class source:
        upstream_version = '1.0~rc3'

    def test_valid_upstream_branch(self):
        """Get upstream tree from a valid upstream branch"""
        self.add_file('foo')
        self.repo.create_branch('upstream')
        options = MockOptions(upstream_tree='BRANCH',
                              upstream_branch='upstream')
        t = export_orig.git_archive_get_upstream_tree(self.repo, None, options)
        self.assertEqual(t, 'upstream')

    def test_invalid_upstream_branch(self):
        """Getting upstream tree from a invalid upstream branch must fail"""
        self.add_file('foo')
        options = MockOptions(upstream_tree='BRANCH',
                              upstream_branch='upstream')
        with self.assertRaises(gbp.errors.GbpError):
            export_orig.git_archive_get_upstream_tree(self.repo, None, options)

    def test_valid_tree(self):
        """Get upstream tree from a valid upstream tree"""
        self.add_file('foo')
        tree = self.repo.rev_parse('master')
        options = MockOptions(upstream_tree=tree)
        t = export_orig.git_archive_get_upstream_tree(self.repo, None, options)
        self.assertEqual(t, tree)

    def test_invalid_tree(self):
        """Getting upstream tree from an invalid tree must fail"""
        self.add_file('foo')
        options = MockOptions(upstream_tree='doesnotexist')
        with self.assertRaises(gbp.errors.GbpError):
            export_orig.git_archive_get_upstream_tree(self.repo, None, options)

    def test_valid_tag(self):
        """Get upstream tree from a valid tag"""
        self.add_file('foo')
        self.repo.rev_parse('master')
        self.repo.create_tag('upstream/1.0_rc3')
        options = MockOptions(upstream_tree="TAG",
                              upstream_tag="upstream/%(version)s")
        tag = export_orig.git_archive_get_upstream_tree(self.repo, self.source, options)
        self.assertEqual(tag, "upstream/1.0_rc3")

    def test_invalid_tag(self):
        """Getting upstream tree from an invalid tag must fail"""
        self.add_file('foo')
        options = MockOptions(upstream_tree="TAG",
                              upstream_tag="upstream/%(version)s")
        with self.assertRaises(gbp.errors.GbpError):
            export_orig.git_archive_get_upstream_tree(self.repo, self.source, options)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
