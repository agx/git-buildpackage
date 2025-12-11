# vim: set fileencoding=utf-8 :

"""Test tarball compression type detection"""

from . import context

import unittest

from gbp.deb.source import DebianSource

from gbp.scripts import export_orig
from gbp.deb import DebianPkgPolicy
from gbp.errors import GbpError


class MockGitRepository:
    def __init__(self, with_branch=False, subject=None):
        self.with_branch = with_branch
        self.subject = subject

    def has_pristine_tar_branch(self):
        return self.with_branch

    def has_branch(self, branch, remote=False):
        return branch == 'pristine-tar' and self.with_branch

    def pristine_tar_branch(self):
        'pristine-tar'

    def grep_log(self, regex, branch, merges=True):
        return None

    def get_commit_info(self, commit):
        return {'subject': self.subject}


class MockedSource(DebianSource):
    def __init__(self):
        pass

    def is_native(self):
        return False

    @property
    def name(self):
        return 'source'

    @property
    def upstream_version(self):
        return '1.2'


class TestDetection(unittest.TestCase):
    def setUp(self):
        self.source = MockedSource()
        self.tmpdir = context.new_tmpdir(__name__)

    def tearDown(self):
        context.teardown()

    def test_guess_comp_type_no_pristine_tar_no_orig(self):
        repo = MockGitRepository(with_branch=False)
        guessed = export_orig.guess_comp_type(
            'auto', self.source, repo, str(self.tmpdir))
        self.assertEqual('gzip', guessed)

    def test_guess_comp_type_no_pristine_tar_with_orig(self):
        open(self.tmpdir.join('source_1.2.orig.tar.bz2'), "w").close()
        repo = MockGitRepository(with_branch=False)
        guessed = export_orig.guess_comp_type(
            'auto', self.source, repo, str(self.tmpdir))
        self.assertEqual('bzip2', guessed)

    def test_guess_comp_type_no_pristine_tar_with_multiple_origs(self):
        open(self.tmpdir.join('source_1.2.orig.tar.gz'), "w").close()
        open(self.tmpdir.join('source_1.2.orig.tar.xz'), "w").close()
        repo = MockGitRepository(with_branch=False)
        with self.assertRaises(GbpError):
            export_orig.guess_comp_type('auto', self.source, repo, str(self.tmpdir))

    def test_guess_comp_type_auto_bzip2(self):
        subject = 'pristine-tar data for source_1.2-3.orig.tar.bz2'
        repo = MockGitRepository(with_branch=True, subject=subject)
        guessed = export_orig.guess_comp_type(
            'auto', self.source, repo, str(self.tmpdir))
        self.assertEqual("bzip2", guessed)

    def test_has_orig_single_false(self):
        self.assertFalse(DebianPkgPolicy.has_origs([self.source.upstream_tarball_name('gzip')], str(self.tmpdir)))

    def test_has_orig_single_true(self):
        open(self.tmpdir.join('source_1.2.orig.tar.gz'), "w").close()
        self.assertTrue(DebianPkgPolicy.has_origs([self.source.upstream_tarball_name('gzip')], str(self.tmpdir)))

    def test_has_orig_multiple_false(self):
        orig_files = [self.source.upstream_tarball_name('gzip')] + \
                     [self.source.upstream_tarball_name('gzip', sub) for sub in ['foo', 'bar']]
        self.assertFalse(DebianPkgPolicy.has_origs(orig_files, str(self.tmpdir)))

    def test_has_orig_multiple_true(self):
        for ext in ['', '-foo', '-bar']:
            open(self.tmpdir.join('source_1.2.orig%s.tar.gz' % ext), "w").close()
        orig_files = [self.source.upstream_tarball_name('gzip')] + \
                     [self.source.upstream_tarball_name('gzip', sub) for sub in ['foo', 'bar']]
        self.assertTrue(DebianPkgPolicy.has_origs(orig_files, str(self.tmpdir)))

    def test_guess_comp_type_bzip2(self):
        repo = MockGitRepository(with_branch=False)
        guessed = export_orig.guess_comp_type(
            'bzip2', self.source, repo, None)
        self.assertEqual("bzip2", guessed)

    def test_guess_comp_type_gzip(self):
        repo = MockGitRepository(with_branch=False)
        guessed = export_orig.guess_comp_type(
            'gzip', self.source, repo, None)
        self.assertEqual("gzip", guessed)

    def test_guess_comp_type_bz(self):
        repo = MockGitRepository(with_branch=False)
        guessed = export_orig.guess_comp_type(
            'xz', self.source, repo, None)
        self.assertEqual("xz", guessed)

    def test_guess_comp_type_lzma(self):
        repo = MockGitRepository(with_branch=False)
        guessed = export_orig.guess_comp_type(
            'lzma', self.source, repo, None)
        self.assertEqual("lzma", guessed)

    def test_guess_comp_type_bz2(self):
        repo = MockGitRepository(with_branch=False)
        guessed = export_orig.guess_comp_type(
            'bz2', self.source, repo, None)
        self.assertEqual("bzip2", guessed)

    def test_guess_comp_type_gz(self):
        repo = MockGitRepository(with_branch=False)
        guessed = export_orig.guess_comp_type(
            'gz', self.source, repo, None)
        self.assertEqual("gzip", guessed)

    def test_guess_comp_type_no_repo(self):
        guessed = export_orig.guess_comp_type(
            'auto', self.source, None, str(self.tmpdir))
        self.assertEqual('gzip', guessed)
