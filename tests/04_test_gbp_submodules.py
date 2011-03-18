# vim: set fileencoding=utf-8 :

import os
import shutil
import tempfile

import gbp.git
import gbp.command_wrappers

top = None

repo = None
repo_dir = None

submodule = None
submodule_dir = None

def setup():
    global repo, repo_dir, submodule, submodule_dir,  top

    top = os.path.abspath(os.curdir)

    repo_dir = os.path.join(top, 'gbp_%s_repo' % __name__)
    repo = gbp.git.create_repo(repo_dir)

    submodule_dir = os.path.join(top, 'gbp_%s_submodule' % __name__)
    submodule = gbp.git.create_repo(submodule_dir)

    os.chdir(repo_dir)


def teardown():
    os.chdir(top)
    if not os.getenv("GBP_TESTS_NOCLEAN"):
        if repo_dir:
            shutil.rmtree(repo_dir)
        if submodule_dir:
            shutil.rmtree(submodule_dir)


def test_empty_has_submodules():
    """Test empty repo for submodules"""
    assert not repo.has_submodules()


def _add_dummy_data():
    shutil.copy(".git/HEAD", "testfile")
    gbp.command_wrappers.GitAdd()(['-f', '.'])
    gbp.command_wrappers.GitCommand("commit", ["-mfoo", "-a"])()


def test_add_files():
    """Add some dummy data"""
    _add_dummy_data()
    assert True


def test_add_submodule_files():
    """Add some dummy data"""
    os.chdir(submodule_dir)
    _add_dummy_data()
    os.chdir(repo_dir)
    assert True


def test_add_submodule():
    """Add a submodule"""
    repo.add_submodule(submodule_dir)
    gbp.command_wrappers.GitCommand("commit",
                                    ["-m 'Added submodule %s'" % submodule_dir,
                                     "-a"])()

def test_has_submodules():
    """Check for submodules"""
    assert repo.has_submodules()


def test_get_submodules():
    """Check for submodules list of  (name, hash)"""
    submodule = repo.get_submodules("master")[0]
    assert submodule[0] == './gbp_04_test_gbp_submodules_submodule'
    assert len(submodule[1]) == 40

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
