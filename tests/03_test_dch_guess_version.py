# vim: set fileencoding=utf-8 :

"""Test L{Changelog}'s guess_version_from_upstream"""

from . import context

import testutils
import unittest

from gbp.scripts import dch
from gbp.deb.changelog import ChangeLog


class MockedChangeLog(ChangeLog):
    contents = """foo (%s) experimental; urgency=low

  * a important change

 -- Debian Maintainer <maint@debian.org>  Sat, 01 Jan 2012 00:00:00 +0100"""

    def __init__(self, version):
        ChangeLog.__init__(self, contents=self.contents % version)


class TestGuessVersionFromUpstream(testutils.DebianGitTestRepo):
    """Test guess_version_from_upstream"""

    def test_guess_no_epoch(self):
        """Guess the new version from the upstream tag"""
        cp = MockedChangeLog('1.0-1')
        tagformat = 'upstream/%(version)s'
        uversion = '1.1'

        self.add_file('doesnot', 'matter')
        tag = self.repo.version_to_tag(tagformat, uversion)
        self.repo.create_tag(name=tag, msg="Upstream release %s" % uversion,
                             sign=False)

        guessed = dch.guess_version_from_upstream(self.repo,
                                                  tagformat,
                                                  cp)
        self.assertEqual('1.1-1', guessed)

    def test_guess_epoch(self):
        """Check if we picked up the epoch correctly (#652366)"""
        cp = MockedChangeLog('1:1.0-1')

        tagformat = 'upstream/%(version)s'
        uversion = '1.1'

        self.add_file('doesnot', 'matter')
        tag = self.repo.version_to_tag(tagformat, uversion)
        self.repo.create_tag(name=tag, msg="Upstream release %s" % uversion,
                             sign=False)

        guessed = dch.guess_version_from_upstream(self.repo,
                                                  tagformat,
                                                  cp)

        self.assertEqual('1:1.1-1', guessed)


