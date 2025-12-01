# vim: set fileencoding=utf-8 :

"""Test submodule L{GitRepository} submodule methods"""

from . import context

import os
import shutil
import tarfile
import unittest

import gbp.log
import gbp.git
import gbp.command_wrappers

from gbp.deb.policy import DebianPkgPolicy as Policy
from gbp.deb.git import DebianGitRepository
from gbp.pkg import Compressor

from gbp.scripts import buildpackage
from tests.testutils import ls_zip

SUBMODULE_NAMES = ["test_submodule", "sub module"]
TESTFILE_NAME = "testfile"
TESTDIR_NAME = "testdir"


class Submodule(object):
    """Class representing remote repo for Git submodule"""
    def __init__(self, name, tmpdir):
        self.name = name
        self.dir = os.path.join(tmpdir, name)
        self.repo = gbp.git.GitRepository.create(self.dir)


def _add_dummy_data(repo, msg):
    """Commit dummy data to a Git repository"""
    shutil.copy(".git/HEAD", TESTFILE_NAME)
    os.mkdir(TESTDIR_NAME)
    shutil.copy(TESTFILE_NAME, os.path.join(TESTDIR_NAME, TESTFILE_NAME))
    repo.add_files('.', force=True)
    repo.commit_all(msg)


class TestSubmodule(unittest.TestCase):
    def setUp(self):
        self.tmpdir = context.new_tmpdir(__name__)
        self.repodir = self.tmpdir.join('test_repo')
        self.repo = DebianGitRepository.create(self.repodir)
        self.submodules = []

        os.environ['GIT_ALLOW_PROTOCOL'] = 'file'
        for name in SUBMODULE_NAMES:
            self.submodules.append(Submodule(name, str(self.tmpdir)))

        context.chdir(self.repodir)

    def tearDown(self):
        context.teardown()
        del os.environ['GIT_ALLOW_PROTOCOL']

    def _add_submodule(self):
        # initialize self.repo
        _add_dummy_data(self.repo, "initial commit")

        # ... and both submodules
        for submodule in self.submodules:
            os.chdir(submodule.dir)
            _add_dummy_data(submodule.repo, "initial commit in submodule")
            os.chdir(self.repodir)

        self.repo.add_submodule(self.submodules[0].dir)
        self.repo.commit_all(msg='Added submodule %s' % self.submodules[0].dir)

    def _add_whitespace_submodule(self):
        """Add a second submodule with name containing whitespace"""
        self.repo.add_submodule(self.submodules[1].dir)
        self.repo.commit_all(msg='Added submodule %s' % self.submodules[0].dir)

    def test_empty_has_submodules(self):
        """Test empty repo for submodules"""
        assert not self.repo.has_submodules()

    def test_has_submodules(self):
        """Check for submodules"""
        self._add_submodule()
        assert self.repo.has_submodules()
        assert self.repo.has_submodules("HEAD")
        assert not self.repo.has_submodules("HEAD^")

    def test_get_submodules(self):
        """Check for submodules list of  (name, hash)"""
        self._add_submodule()
        name, hash = self.repo.get_submodules("master")[0]
        assert name == "test_submodule"
        assert len(hash) == 40

    def test_dump_tree(self):
        """Dump the repository and check if files exist"""
        self._add_submodule()

        dumpdir = self.tmpdir.join("dump")
        os.mkdir(dumpdir)
        assert buildpackage.dump_tree(self.repo, dumpdir, "master", True)
        assert os.path.exists(os.path.join(dumpdir, TESTFILE_NAME))
        assert os.path.exists(os.path.join(dumpdir, TESTDIR_NAME, TESTFILE_NAME))
        assert os.path.exists(os.path.join(dumpdir, self.submodules[0].name, TESTFILE_NAME))
        # No submodules or subdirs if recursive is False
        dumpdir = self.tmpdir.join("dump2")
        os.mkdir(dumpdir)
        assert buildpackage.dump_tree(self.repo, dumpdir, "master", True, False)
        assert os.path.exists(os.path.join(dumpdir, TESTFILE_NAME))
        assert not os.path.exists(os.path.join(dumpdir, TESTDIR_NAME))
        assert not os.path.exists(os.path.join(dumpdir, self.submodules[0].name))

    def test_create_zip_archives(self):
        """Create an upstream zip archive"""
        self._add_submodule()

        self.repo.archive_comp(
            'HEAD', 'with-submodules.zip', 'test', None, format='zip', submodules=True
        )
        # Check that submodules were included
        contents = ls_zip("with-submodules.zip")
        assert "test/test_submodule/testfile" in contents

        self.repo.archive_comp(
            "HEAD", "without-submodules.zip", "test", None, format="zip", submodules=False
        )
        contents = ls_zip("without-submodules.zip")
        assert "test/test_submodule/testfile" not in contents

    def test_check_tarfiles(self):
        """Check the contents of a created tarfile"""
        class MockedSource:
            def __init__(self, version):
                self.name = 'test'
                self.upstream_version = version

            def upstream_tarball_name(self, compression, component=None):
                return Policy.build_tarball_name(self.name,
                                                 self.upstream_version,
                                                 compression=compression)

        self._add_submodule()

        # Create some upstream tarballs
        comp = Compressor('bzip2')
        # Tarball with submodules
        s = MockedSource("0.1")
        assert self.repo.create_upstream_tarball_via_git_archive(
            s, str(self.tmpdir), "HEAD", comp, with_submodules=True
        )
        # Tarball without submodules
        s = MockedSource("0.2")
        assert self.repo.create_upstream_tarball_via_git_archive(
            s, str(self.tmpdir), "HEAD", comp, with_submodules=False
        )

        # Check tarball with submodules
        tarobj = tarfile.open(self.tmpdir.join("test_0.1.orig.tar.bz2"), 'r:*')
        files = tarobj.getmembers()
        assert "test-0.1/.gitmodules" in [f.name for f in files]
        assert len(files) == 10
        # Check tarball without submodules
        tarobj = tarfile.open(self.tmpdir.join("test_0.2.orig.tar.bz2"), 'r:*')
        files = tarobj.getmembers()
        assert ("test-0.2/%s" % TESTFILE_NAME) in [f.name for f in files]
        assert len(files) == 6

    def test_get_more_submodules(self):
        """Check for submodules list of  (name, hash)"""
        self._add_submodule()
        self._add_whitespace_submodule()

        module = self.repo.get_submodules("master")
        assert len(module) == len(SUBMODULE_NAMES)
        for name, hash in self.repo.get_submodules("master"):
            assert len(hash) == 40
            assert os.path.basename(name) in SUBMODULE_NAMES

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
