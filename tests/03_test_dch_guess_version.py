import unittest

from gbp.scripts import dch
from gbp.errors import GbpError
from gbp.deb.changelog import ChangeLog
from gbp.deb.git import DebianGitRepository

class MockGitRepository(object):
    def __init__(self, upstream_tag):
        self.upstream_tag = upstream_tag

    def find_tag(self, branch, pattern):
        return self.upstream_tag

    def tag_to_version(self, tag, format):
        return DebianGitRepository.tag_to_version(tag, format)


class MockedChangeLog(ChangeLog):
    contents = """foo (%s) experimental; urgency=low

  * a important change

 -- Debian Maintainer <maint@debian.org>  Sat, 01 Jan 2012 00:00:00 +0100"""

    def __init__(self, version):
        ChangeLog.__init__(self, contents=self.contents % version)


class TestGuessVersionFromUpstream(unittest.TestCase):
    """Dest guess_version_from_upstream"""
    def test_guess_no_epoch(self):
        """Guess the new version from the upstream tag"""
        repo = MockGitRepository(upstream_tag='upstream/1.1')
        cp = MockedChangeLog('1.0-1')
        guessed = dch.guess_version_from_upstream(repo,
                                                  'upstream/%(version)s',
                                                  cp)
        self.assertEqual('1.1-1', guessed)

    def test_guess_epoch(self):
        """Check if we picked up the epoch correctly (#652366)"""
        repo = MockGitRepository(upstream_tag='upstream/1.1')
        cp = MockedChangeLog('1:1.0-1')
        guessed = dch.guess_version_from_upstream(repo,
                                                  'upstream/%(version)s',
                                                  cp)
        self.assertEqual('1:1.1-1', guessed)


