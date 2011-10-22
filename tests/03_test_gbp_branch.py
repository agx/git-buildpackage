# vim: set fileencoding=utf-8 :

import os
import shutil
import tempfile

import gbp.git
import gbp.command_wrappers

repo = None
repo_dir = None
top = None

def setup():
    global repo, repo_dir, top

    top = os.path.abspath(os.curdir)
    repo_dir = os.path.join(top, 'gbp_%s_test_repo' % __name__)
    repo = gbp.git.GitRepository.create(repo_dir)
    os.chdir(repo_dir)


def teardown():
    os.chdir(top)
    if not os.getenv("GBP_TESTS_NOCLEAN") and repo_dir:
        shutil.rmtree(repo_dir)


def test_branch():
    """Empty repos have no branch"""
    assert repo.get_branch() == None


def test_is_empty():
    """Repo is still empty"""
    assert repo.is_empty()


def test_add_files():
    """Add some dummy data"""
    shutil.copy(".git/HEAD", "testfile")
    repo.add_files('.', force=True)
    repo.commit_all(msg="foo")
    assert True

def test_branch_master():
    """First branch is master"""
    assert repo.get_branch() == "master"

def test_create_branch_foo():
    """Create branch foo"""
    repo.create_branch("foo")

def test_set_branch_foo():
    """Switch to branch foo"""
    repo.set_branch("foo")
    assert repo.get_branch() == "foo"

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
