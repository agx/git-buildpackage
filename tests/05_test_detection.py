import os
import shutil
import tempfile
import unittest

import git_buildpackage
from gbp.deb import has_orig
from gbp.errors import GbpError

class MockGitRepository:
    def __init__(self, with_branch=False, subject=None):
        self.with_branch = with_branch
        self.subject = subject

    def has_branch(self, branch):
        return self.with_branch

    def grep_log(self, regex, branch):
        return None

    def get_subject(self, commit):
        return self.subject

class TestDetection(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cp = {'Source': 'source', 'Upstream-Version': '1.2'}

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_guess_comp_type_no_pristine_tar_no_orig(self):
        repo = MockGitRepository(with_branch=False)
        guessed = git_buildpackage.guess_comp_type(
            repo, 'auto', self.cp, self.tmpdir)
        self.assertEqual('gzip', guessed)

    def test_guess_comp_type_no_pristine_tar_with_orig(self):
        open(os.path.join(self.tmpdir, 'source_1.2.orig.tar.bz2'), "w").close()
        repo = MockGitRepository(with_branch=False)
        guessed = git_buildpackage.guess_comp_type(
            repo, 'auto', self.cp, self.tmpdir)
        self.assertEqual('bzip2', guessed)

    def test_guess_comp_type_no_pristine_tar_with_multiple_origs(self):
        open(os.path.join(self.tmpdir, 'source_1.2.orig.tar.gz'), "w").close()
        open(os.path.join(self.tmpdir, 'source_1.2.orig.tar.xz'), "w").close()
        repo = MockGitRepository(with_branch=False)
        self.assertRaises(
            GbpError,
            git_buildpackage.guess_comp_type,
            repo,
            'auto',
            self.cp,
            self.tmpdir)

    def test_guess_comp_type_auto_bzip2(self):
        subject = 'pristine-tar data for source_1.2-3.orig.tar.bz2'
        repo = MockGitRepository(with_branch=True, subject=subject)
        guessed = git_buildpackage.guess_comp_type(
            repo, 'auto', self.cp, self.tmpdir)
        self.assertEqual("bzip2", guessed)

    def test_has_orig_false(self):
        self.assertFalse(has_orig(self.cp, 'gzip', self.tmpdir))

    def test_has_orig_true(self):
        open(os.path.join(self.tmpdir, 'source_1.2.orig.tar.gz'), "w").close()
        self.assertTrue(has_orig(self.cp, 'gzip', self.tmpdir))

    def test_guess_comp_type_bzip2(self):
        repo = MockGitRepository(with_branch=False)
        guessed = git_buildpackage.guess_comp_type(
            repo, 'bzip2', self.cp, None)
        self.assertEqual("bzip2", guessed)

    def test_guess_comp_type_gzip(self):
        repo = MockGitRepository(with_branch=False)
        guessed = git_buildpackage.guess_comp_type(
            repo, 'gzip', self.cp, None)
        self.assertEqual("gzip", guessed)

    def test_guess_comp_type_bz(self):
        repo = MockGitRepository(with_branch=False)
        guessed = git_buildpackage.guess_comp_type(
            repo, 'xz', self.cp, None)
        self.assertEqual("xz", guessed)

    def test_guess_comp_type_lzma(self):
        repo = MockGitRepository(with_branch=False)
        guessed = git_buildpackage.guess_comp_type(
            repo, 'lzma', self.cp, None)
        self.assertEqual("lzma", guessed)
