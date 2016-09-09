# vim: set fileencoding=utf-8 :

"""Test submodule L{GitRepository} submodule methods"""

from . import context

import os
import shutil
import tarfile
from nose.tools import eq_, ok_

import gbp.log
import gbp.git
import gbp.command_wrappers

from gbp.scripts import buildpackage
from gbp.scripts.common.buildpackage import (git_archive_submodules,
                                             git_archive_single)
from tests.testutils import ls_zip

REPO = None
REPODIR = None

SUBMODULES = []
SUBMODULE_NAMES = ["test_submodule", "sub module"]
TMPDIR = None
TESTFILE_NAME = "testfile"
TESTDIR_NAME = "testdir"


class Submodule(object):
    """Class representing remote repo for Git submodule"""
    def __init__(self, name, tmpdir):
        self.name = name
        self.dir = os.path.join(tmpdir, name)
        self.repo = gbp.git.GitRepository.create(self.dir)


def setup():
    """Test module setup"""
    global REPO, REPODIR, SUBMODULES, TMPDIR

    TMPDIR = context.new_tmpdir(__name__)
    REPODIR = TMPDIR.join('test_repo')
    REPO = gbp.git.GitRepository.create(REPODIR)

    for name in SUBMODULE_NAMES:
        SUBMODULES.append(Submodule(name, str(TMPDIR)))

    context.chdir(REPODIR)


def teardown():
    """Test module teardown"""
    context.teardown()


def test_empty_has_submodules():
    """Test empty repo for submodules"""
    ok_(not REPO.has_submodules())


def _add_dummy_data(repo, msg):
    """Commit dummy data to a Git repository"""
    shutil.copy(".git/HEAD", TESTFILE_NAME)
    os.mkdir(TESTDIR_NAME)
    shutil.copy(TESTFILE_NAME, os.path.join(TESTDIR_NAME, TESTFILE_NAME))
    repo.add_files('.', force=True)
    repo.commit_all(msg)


def test_add_files():
    """Add some dummy data"""
    _add_dummy_data(REPO, "initial commit")
    ok_(True)


def test_add_submodule_files():
    """Add some dummy data"""
    for submodule in SUBMODULES:
        os.chdir(submodule.dir)
        _add_dummy_data(submodule.repo, "initial commit in submodule")
        os.chdir(REPODIR)
    ok_(True)


def test_add_submodule():
    """Add a submodule"""
    REPO.add_submodule(SUBMODULES[0].dir)
    REPO.commit_all(msg='Added submodule %s' % SUBMODULES[0].dir)


def test_has_submodules():
    """Check for submodules"""
    ok_(REPO.has_submodules())
    ok_(REPO.has_submodules('HEAD'))
    ok_(not REPO.has_submodules('HEAD^'))


def test_get_submodules():
    """Check for submodules list of  (name, hash)"""
    modules = REPO.get_submodules("master")[0]
    eq_(modules[0], 'test_submodule')
    eq_(len(modules[1]), 40)


def test_dump_tree():
    """Dump the repository and check if files exist"""
    dumpdir = TMPDIR.join("dump")
    os.mkdir(dumpdir)
    ok_(buildpackage.dump_tree(REPO, dumpdir, "master", True))
    ok_(os.path.exists(os.path.join(dumpdir, TESTFILE_NAME)))
    ok_(os.path.exists(os.path.join(dumpdir, TESTDIR_NAME, TESTFILE_NAME)))
    ok_(os.path.exists(os.path.join(dumpdir, SUBMODULES[0].name,
                                    TESTFILE_NAME)))
    # No submodules or subdirs if recursive is False
    dumpdir = TMPDIR.join("dump2")
    os.mkdir(dumpdir)
    ok_(buildpackage.dump_tree(REPO, dumpdir, "master", True, False))
    ok_(os.path.exists(os.path.join(dumpdir, TESTFILE_NAME)))
    ok_(not os.path.exists(os.path.join(dumpdir, TESTDIR_NAME)))
    ok_(not os.path.exists(os.path.join(dumpdir, SUBMODULES[0].name)))


def test_create_tarballs():
    """Create an upstream tarball"""
    # Tarball with submodules
    changelog = {"Source": "test", "Upstream-Version": "0.1"}
    ok_(buildpackage.git_archive(REPO, changelog, str(TMPDIR), "HEAD", "bzip2",
                                 "9", True))
    # Tarball without submodules
    changelog = {"Source": "test", "Upstream-Version": "0.2"}
    ok_(buildpackage.git_archive(REPO, changelog, str(TMPDIR), "HEAD", "bzip2",
                                 "9", False))


def test_create_zip_archives():
    """Create an upstream zip archive"""
    git_archive_submodules(REPO, 'HEAD', 'with-submodules.zip', 'test',
                           '', '', '', 'zip')
    # Check that submodules were included
    contents = ls_zip('with-submodules.zip')
    ok_('test/test_submodule/testfile' in contents)

    git_archive_single('HEAD', 'without-submodules.zip', 'test',
                       '', '', '', 'zip')
    contents = ls_zip('without-submodules.zip')
    ok_('test/test_submodule/testfile' not in contents)


def test_check_tarfiles():
    """Check the contents of the created tarfile"""
    # Check tarball with submodules
    tarobj = tarfile.open(TMPDIR.join("test_0.1.orig.tar.bz2"), 'r:*')
    files = tarobj.getmembers()
    ok_("test-0.1/.gitmodules" in [f.name for f in files])
    eq_(len(files), 10)
    # Check tarball without submodules
    tarobj = tarfile.open(TMPDIR.join("test_0.2.orig.tar.bz2"), 'r:*')
    files = tarobj.getmembers()
    ok_(("test-0.2/%s" % TESTFILE_NAME) in [f.name for f in files])
    eq_(len(files), 6)


def test_add_whitespace_submodule():
    """Add a second submodule with name containing whitespace"""
    REPO.add_submodule(SUBMODULES[1].dir)
    REPO.commit_all(msg='Added submodule %s' % SUBMODULES[0].dir)


def test_get_more_submodules():
    """Check for submodules list of  (name, hash)"""
    module = REPO.get_submodules("master")
    eq_(len(module), len(SUBMODULE_NAMES))
    for module in REPO.get_submodules("master"):
        eq_(len(module[1]), 40)
        ok_(os.path.basename(module[0]) in SUBMODULE_NAMES)


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
