# vim: set fileencoding=utf-8 :

"""Test  L{buildpackage}'s get_upstream_tree method"""

import tests.testutils as testutils

import gbp.errors
import gbp.scripts.buildpackage as buildpackage

class MockOptions(object):
    def __init__(self,
                 upstream_branch=None,
                 upstream_tree=None,
                 upstream_tag=None):
        self.upstream_branch = upstream_branch
        self.upstream_tree = upstream_tree
        self.upstream_tag = upstream_tag

class TestGetUpstreamTree(testutils.DebianGitTestRepo):
    def test_valid_upstream_branch(self):
        """Write out index file to nonexistant dir"""
        self.add_file('foo')
        self.repo.create_branch('upstream')
        options = MockOptions(upstream_tree='BRANCH',
                              upstream_branch='upstream')
        t = buildpackage.get_upstream_tree(self.repo, None, options)
        self.assertEqual(t, 'upstream')

    def test_invalid_upstream_branch(self):
        """Write out index file to nonexistant dir"""
        self.add_file('foo')
        options = MockOptions(upstream_tree='BRANCH',
                              upstream_branch='upstream')
        self.assertRaises(gbp.errors.GbpError,
                          buildpackage.get_upstream_tree,
                          self.repo,
                          None,
                          options)

    def test_valid_tree(self):
        """Write out index file to nonexistant dir"""
        self.add_file('foo')
        tree = self.repo.rev_parse('master')
        options = MockOptions(upstream_tree=tree)
        t = buildpackage.get_upstream_tree(self.repo, None, options)
        self.assertEqual(t, tree)

    def test_invalid_tree(self):
        """Write out index file to nonexistant dir"""
        self.add_file('foo')
        options = MockOptions(upstream_tree='doesnotexist')
        self.assertRaises(gbp.errors.GbpError,
                          buildpackage.get_upstream_tree,
                          self.repo,
                          None,
                          options)

    def test_valid_tag(self):
        """Write out index file to nonexistant dir"""
        self.add_file('foo')
        self.repo.rev_parse('master')
        cp = { 'Upstream-Version': '1.0~rc3' }
        self.repo.create_tag('upstream/1.0_rc3')
        options = MockOptions(upstream_tree="TAG",
                              upstream_tag="upstream/%(version)s")
        tag = buildpackage.get_upstream_tree(self.repo, cp, options)
        self.assertEqual(tag, "upstream/1.0_rc3")

    def test_invalid_tag(self):
        """Write out index file to nonexistant dir"""
        self.add_file('foo')
        cp = { 'Upstream-Version': '1.0~rc3' }
        options = MockOptions(upstream_tree="TAG",
                              upstream_tag="upstream/%(version)s")
        self.assertRaises(gbp.errors.GbpError,
                          buildpackage.get_upstream_tree,
                          self.repo,
                          cp,
                          options)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
