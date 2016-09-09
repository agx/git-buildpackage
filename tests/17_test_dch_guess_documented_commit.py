# vim: set fileencoding=utf-8 :

"""Test L{Changelog}'s guess_version_from_upstream"""

from . import context  # noqa: 401
from . import testutils

from gbp.scripts import dch


class TestGuessDocumentedCommit(testutils.DebianGitTestRepo):
    def setUp(self):
        self.version = '1.0-1'
        self.tagformat = 'debian/%(version)s'

        testutils.DebianGitTestRepo.setUp(self)

    def test_01_from_snapshot_banner(self):
        """
        Guess the commit to start from from the snapshot banner
        """
        cp = testutils.MockedChangeLog(self.version,
                                       "*** SNAPSHOT build @12345 ***")
        guessed_commit = dch.guess_documented_commit(cp, None, None)
        self.assertEqual(guessed_commit, '12345')

    def test_02_from_tag(self):
        """
        Guess the commit to start from from the tag matching
        the topmost version in the changelog
        """
        cp = testutils.MockedChangeLog(self.version)

        self.add_file('doesnot', 'matter')
        tag = self.repo.version_to_tag(self.tagformat,
                                       self.version)
        self.repo.create_tag(name=tag,
                             msg="Debian release %s" % self.version,
                             sign=False)
        commit = self.repo.rev_parse('%s^0' % tag)
        guessed_commit = dch.guess_documented_commit(cp,
                                                     self.repo,
                                                     self.tagformat)
        self.assertEqual(guessed_commit, commit)

    def test_03_from_changelog_commit(self):
        """
        Guess the commit to start from from the commit that
        last touched the changelog
        """
        cp = testutils.MockedChangeLog(self.version)

        self.add_file('debian/changelog', 'foo')
        commit = self.repo.head
        self.add_file('doesnot', 'matter')
        guessed_commit = dch.guess_documented_commit(cp,
                                                     self.repo,
                                                     self.tagformat)
        self.assertEqual(guessed_commit, commit)

    def test_04_not_touched(self):
        """
        None of the above matched so we want to start from
        the beginning of history
        """
        cp = testutils.MockedChangeLog(self.version)

        self.add_file('doesnot', 'matter')
        self.add_file('doesnot', 'mattereither')
        guessed_commit = dch.guess_documented_commit(cp,
                                                     self.repo,
                                                     self.tagformat)
        self.assertIsNone(guessed_commit)
