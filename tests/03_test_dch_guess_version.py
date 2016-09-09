# vim: set fileencoding=utf-8 :

"""Test L{Changelog}'s guess_version_from_upstream"""

from . import context  # noqa: F401
from . import testutils

from gbp.scripts import dch


class TestGuessVersionFromUpstream(testutils.DebianGitTestRepo):
    """Test guess_version_from_upstream"""

    def test_guess_no_epoch(self):
        """Guess the new version from the upstream tag"""
        cp = testutils.MockedChangeLog('1.0-1')
        tagformat = 'upstream/%(version)s'
        uversion = '1.1'
        upstream_branch = 'upstream'

        self.add_file('doesnot', 'matter')
        self.repo.create_branch('upstream')
        tag = self.repo.version_to_tag(tagformat, uversion)
        self.repo.create_tag(name=tag, msg="Upstream release %s" % uversion,
                             sign=False)
        self.repo.set_branch("master")
        guessed = dch.guess_version_from_upstream(self.repo,
                                                  tagformat,
                                                  upstream_branch,
                                                  cp)
        self.assertEqual('1.1-1', guessed)

    def test_guess_epoch(self):
        """Check if we picked up the epoch correctly (#652366)"""
        cp = testutils.MockedChangeLog('1:1.0-1')

        tagformat = 'upstream/%(version)s'
        uversion = '1.1'
        upstream_branch = 'upstream'

        self.add_file('doesnot', 'matter')
        self.repo.create_branch('upstream')
        tag = self.repo.version_to_tag(tagformat, uversion)
        self.repo.create_tag(name=tag, msg="Upstream release %s" % uversion,
                             sign=False)

        self.repo.set_branch("master")
        guessed = dch.guess_version_from_upstream(self.repo,
                                                  tagformat,
                                                  upstream_branch,
                                                  cp)

        self.assertEqual('1:1.1-1', guessed)

    def test_guess_upstream_tag_clash_with_non_upstream_tag(self):
        """Guess with clashing upstream- and non-upstream-tag"""
        cp = testutils.MockedChangeLog('0.9-1')

        tagformat = 'v%(version)s'
        uversion = '1.0'
        upstream_branch = 'upstream'

        self.add_file('doesnot', 'matter')
        self.repo.create_branch('upstream')
        tag = self.repo.version_to_tag(tagformat, uversion)
        self.repo.create_tag(name=tag, msg="Upstream release %s" % uversion,
                             sign=False)
        self.repo.set_branch("master")
        self.add_file("clash", "bar")
        self.repo.create_tag("vyatta/something", msg="some non-upstream tag but not package release tag either")
        self.add_file("clash2", "bar")

        guessed = dch.guess_version_from_upstream(self.repo,
                                                  tagformat,
                                                  upstream_branch,
                                                  cp)

        self.assertEqual('1.0-1', guessed)

    def test_guess_upstream_tag_zero_release(self):
        """Guess with existing -0... releases"""
        cp = testutils.MockedChangeLog('0.9-0vyatta2')

        tagformat = 'upstream/%(version)s'
        uversion = '0.9'
        upstream_branch = 'upstream'

        self.add_file('doesnot', 'matter')
        self.repo.create_branch('upstream')
        tag = self.repo.version_to_tag(tagformat, uversion)
        self.repo.create_tag(name=tag, msg="Upstream release %s" % uversion,
                             sign=False)
        self.repo.set_branch('master')
        self.add_file('doesnot2', 'matter')

        guessed = dch.guess_version_from_upstream(self.repo,
                                                  tagformat,
                                                  upstream_branch,
                                                  cp)
        self.assertEqual(None, guessed)
