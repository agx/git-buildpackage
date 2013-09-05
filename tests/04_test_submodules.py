# vim: set fileencoding=utf-8 :

"""Test submodule L{GitRepository} submodule methods"""

from . import context

import os
import shutil
import tarfile
import tempfile
from nose.tools import eq_, ok_

import gbp.log
import gbp.git
import gbp.command_wrappers

from gbp.scripts import buildpackage

repo = None
repodir = None

submodules = []
submodule_names = ["test_submodule", "sub module"]
tmpdir = None
testfile_name = "testfile"

class Submodule(object):
    def __init__(self, name, tmpdir):
        self.name = name
        self.dir = os.path.join(tmpdir, name)
        self.repo = gbp.git.GitRepository.create(self.dir)


def setup():
    global repo, repodir, submodules, tmpdir

    tmpdir = context.new_tmpdir(__name__)
    repodir = tmpdir.join('test_repo')
    repo = gbp.git.GitRepository.create(repodir)

    for name in submodule_names:
        submodules.append(Submodule(name, str(tmpdir)))

    context.chdir(repodir)


def teardown():
    context.teardown()

def test_empty_has_submodules():
    """Test empty repo for submodules"""
    ok_(not repo.has_submodules())


def _add_dummy_data(repo, msg):
    shutil.copy(".git/HEAD", testfile_name)
    repo.add_files('.', force=True)
    repo.commit_all(msg)


def test_add_files():
    """Add some dummy data"""
    _add_dummy_data(repo, "initial commit")
    ok_(True)


def test_add_submodule_files():
    """Add some dummy data"""
    for submodule in submodules:
        os.chdir(submodule.dir)
        _add_dummy_data(submodule.repo, "initial commit in submodule")
        os.chdir(repodir)
    ok_(True)


def test_add_submodule():
    """Add a submodule"""
    repo.add_submodule(submodules[0].dir)
    repo.commit_all(msg='Added submodule %s' % submodules[0].dir)

def test_has_submodules():
    """Check for submodules"""
    ok_(repo.has_submodules())


def test_get_submodules():
    """Check for submodules list of  (name, hash)"""
    modules = repo.get_submodules("master")[0]
    eq_(modules[0] , 'test_submodule')
    eq_(len(modules[1]) , 40)


def test_dump_tree():
    """Dump the repository and check if files exist"""
    dumpdir = tmpdir.join("dump")
    os.mkdir(dumpdir)
    ok_(buildpackage.dump_tree(repo, dumpdir, "master", True))
    ok_(os.path.exists(os.path.join(dumpdir, testfile_name)))
    ok_(os.path.exists(os.path.join(dumpdir, submodules[0].name,
                                    testfile_name)))


def test_create_tarballs():
    """Create an upstream tarball"""
    # Tarball with submodules
    changelog = { "Source": "test", "Upstream-Version": "0.1" }
    ok_(buildpackage.git_archive(repo, changelog, str(tmpdir), "HEAD", "bzip2",
                                 "9", True))
    # Tarball without submodules
    changelog = { "Source": "test", "Upstream-Version": "0.2" }
    ok_(buildpackage.git_archive(repo, changelog, str(tmpdir), "HEAD", "bzip2",
                                 "9", False))

def test_check_tarfiles():
    """Check the contents of the created tarfile"""
    # Check tarball with submodules
    tarobj = tarfile.open(tmpdir.join("test_0.1.orig.tar.bz2"), 'r:*')
    files = tarobj.getmembers()
    ok_("test-0.1/.gitmodules" in [ f.name for f in files ])
    eq_(len(files) , 6)
    # Check tarball without submodules
    tarobj = tarfile.open(tmpdir.join("test_0.2.orig.tar.bz2"), 'r:*')
    files = tarobj.getmembers()
    ok_(("test-0.2/%s" % testfile_name) in [ f.name for f in files ])
    eq_(len(files) , 4)

def test_add_whitespace_submodule():
    """Add a second submodule with name containing whitespace"""
    repo.add_submodule(submodules[1].dir)
    repo.commit_all(msg='Added submodule %s' % submodules[0].dir)

def test_get_more_submodules():
    """Check for submodules list of  (name, hash)"""
    module = repo.get_submodules("master")
    eq_(len(module), len(submodule_names))
    for module in repo.get_submodules("master"):
        eq_(len(module[1]) , 40)
        ok_(os.path.basename(module[0]) in submodule_names)


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
