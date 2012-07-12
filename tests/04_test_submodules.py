# vim: set fileencoding=utf-8 :

"""Test submodule L{GitRepository} submodule methods"""

import os
import shutil
import tarfile

import gbp.log
import gbp.git
import gbp.command_wrappers

from gbp.scripts import buildpackage

top = None
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
    global repo, repodir, submodules, top, tmpdir

    gbp.log.setup(False, False)
    top = os.path.abspath(os.curdir)
    tmpdir =os.path.join(top,'gbp_%s_repo' % __name__)
    os.mkdir(tmpdir)

    repodir = os.path.join(tmpdir, 'test_repo')
    repo = gbp.git.GitRepository.create(repodir)

    for name in submodule_names:
        submodules.append(Submodule(name, tmpdir))

    os.chdir(repodir)


def teardown():
    os.chdir(top)
    if not os.getenv("GBP_TESTS_NOCLEAN") and tmpdir:
        shutil.rmtree(tmpdir)


def test_empty_has_submodules():
    """Test empty repo for submodules"""
    assert not repo.has_submodules()


def _add_dummy_data(repo, msg):
    shutil.copy(".git/HEAD", testfile_name)
    repo.add_files('.', force=True)
    repo.commit_all(msg)


def test_add_files():
    """Add some dummy data"""
    _add_dummy_data(repo, "initial commit")
    assert True


def test_add_submodule_files():
    """Add some dummy data"""
    for submodule in submodules:
        os.chdir(submodule.dir)
        _add_dummy_data(submodule.repo, "initial commit in submodule")
        os.chdir(repodir)
    assert True


def test_add_submodule():
    """Add a submodule"""
    repo.add_submodule(submodules[0].dir)
    repo.commit_all(msg='Added submodule %s' % submodules[0].dir)

def test_has_submodules():
    """Check for submodules"""
    assert repo.has_submodules()


def test_get_submodules():
    """Check for submodules list of  (name, hash)"""
    modules = repo.get_submodules("master")[0]
    assert modules[0] == 'test_submodule'
    assert len(modules[1]) == 40


def test_dump_tree():
    """Dump the repository and check if files exist"""
    dumpdir = os.path.join(tmpdir, "dump")
    os.mkdir(dumpdir)
    assert buildpackage.dump_tree(repo, dumpdir, "master", True)
    assert os.path.exists(os.path.join(dumpdir, testfile_name))
    assert os.path.exists(os.path.join(dumpdir, submodules[0].name, testfile_name))


def test_create_tarball():
    """Create an upstream tarball"""
    cp = { "Source": "test", "Upstream-Version": "0.1" }
    assert buildpackage.git_archive(repo,
                                        cp,
                                        tmpdir,
                                        "HEAD",
                                        "bzip2",
                                        "9",
                                        True)

def test_check_tarfile():
    """Check the contents of the created tarfile"""
    t = tarfile.open(os.path.join(tmpdir,"test_0.1.orig.tar.bz2"), 'r:*')
    files = t.getmembers()
    assert "test-0.1/.gitmodules" in [ f.name for f in files ]
    assert len(files) == 6

def test_add_whitespace_submodule():
    """Add a second submodule with name containing whitespace"""
    repo.add_submodule(submodules[1].dir)
    repo.commit_all(msg='Added submodule %s' % submodules[0].dir)

def test_get_more_submodules():
    """Check for submodules list of  (name, hash)"""
    module = repo.get_submodules("master")
    assert(len(module) == len(submodule_names))
    for module in repo.get_submodules("master"):
        assert len(module[1]) == 40
        assert os.path.basename(module[0]) in submodule_names


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
