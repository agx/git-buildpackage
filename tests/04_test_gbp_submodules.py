# vim: set fileencoding=utf-8 :

import os
import shutil
import tempfile

import gbp.git
import gbp.command_wrappers

import git_buildpackage

top = None

repo = None
repodir = None

submodule = None
submoduledir = None
submodule_name = "test_submodule"

tmpdir = None
testfile_name = "testfile"


def setup():
    global repo, repodir, submodule, submoduledir,  top, tmpdir

    top = os.path.abspath(os.curdir)
    tmpdir =os.path.join(top,'gbp_%s_repo' % __name__)
    os.mkdir(tmpdir)

    repodir = os.path.join(tmpdir, 'test_repo')
    repo = gbp.git.create_repo(repodir)

    submoduledir = os.path.join(tmpdir, submodule_name)
    submodule = gbp.git.create_repo(submoduledir)

    os.chdir(repodir)


def teardown():
    os.chdir(top)
    if not os.getenv("GBP_TESTS_NOCLEAN") and tmpdir:
        shutil.rmtree(tmpdir)


def test_empty_has_submodules():
    """Test empty repo for submodules"""
    assert not repo.has_submodules()


def _add_dummy_data(msg):
    shutil.copy(".git/HEAD", testfile_name)
    gbp.command_wrappers.GitAdd()(['-f', '.'])
    gbp.command_wrappers.GitCommand("commit", ["-m%s" % msg, "-a"])()


def test_add_files():
    """Add some dummy data"""
    _add_dummy_data("initial commit")
    assert True


def test_add_submodule_files():
    """Add some dummy data"""
    os.chdir(submoduledir)
    _add_dummy_data("initial commit in submodule")
    os.chdir(repodir)
    assert True


def test_add_submodule():
    """Add a submodule"""
    repo.add_submodule(submoduledir)
    gbp.command_wrappers.GitCommand("commit",
                                    ["-m 'Added submodule %s'" % submoduledir,
                                     "-a"])()

def test_has_submodules():
    """Check for submodules"""
    assert repo.has_submodules()


def test_get_submodules():
    """Check for submodules list of  (name, hash)"""
    submodule = repo.get_submodules("master")[0]
    assert submodule[0] == './test_submodule'
    assert len(submodule[1]) == 40


def test_dump_tree():
    """Dump the repository and check if files exist"""
    dumpdir = os.path.join(tmpdir, "dump")
    os.mkdir(dumpdir)
    assert git_buildpackage.dump_tree(repo, dumpdir, "master")
    assert os.path.exists(os.path.join(dumpdir, testfile_name))
    assert os.path.exists(os.path.join(dumpdir, submodule_name, testfile_name))


def test_create_tarball():
    """Create an upstream tarball"""
    cp = { "Source": "test", "Upstream-Version": "0.1" }
    assert git_buildpackage.git_archive(repo,
                                        cp,
                                        tmpdir,
                                        "HEAD",
                                        "bzip2",
                                        "9")

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
