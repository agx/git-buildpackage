# vim: set fileencoding=utf-8 :

"""
Test L{gbp.git.GitRepository}

This testcase creates several repositores:

    - A repository at L{repo_dir} called I{repo}
    - A bare repository at L{bare_dir} called I{bare}
    - A clone of I{repo} below L{clone_dir} called I{clone}
    - A mirror of I{repo} below L{mirror_clone_dir} called I{mirror}
"""

import os
repo_dir = os.path.abspath(
             os.path.join(os.path.curdir, 'gbp_%s_test_repo' % __name__))
bare_dir = os.path.abspath(
             os.path.join(os.path.curdir, 'gbp_%s_test_bare' % __name__))
clone_dir = os.path.abspath(
             os.path.join(os.path.curdir, 'gbp_%s_test_clone' % __name__))
mirror_clone_dir = os.path.abspath(
             os.path.join(os.path.curdir, 'gbp_%s_test_mirror_clone' % __name__))


def test_create():
    """
    Create a repository

    Methods tested:
         - L{gbp.git.GitRepository.create}

    Properties tested:
         - L{gbp.git.GitRepository.path}
         - L{gbp.git.GitRepository.git_dir}

    >>> import os, gbp.git
    >>> repo = gbp.git.GitRepository.create(repo_dir)
    >>> repo.path == repo_dir
    True
    >>> repo.git_dir == os.path.join(repo_dir, '.git')
    True
    >>> type(repo) == gbp.git.GitRepository
    True
    """


def test_empty():
    """
    Empty repos have no branch

    Methods tested:
         - L{gbp.git.GitRepository.get_branch}
         - L{gbp.git.GitRepository.is_empty}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> repo.get_branch()
    >>> repo.branch
    >>> repo.is_empty()
    True
    """


def test_add_files():
    """
    Add some dummy data

    Methods tested:
         - L{gbp.git.GitRepository.add_files}
         - L{gbp.git.GitRepository.commit_all}
         - L{gbp.git.GitRepository.is_clean}

    Properties tested:
         - L{gbp.git.GitRepository.head}

    >>> import gbp.git, shutil
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> shutil.copy(os.path.join(repo.path, ".git/HEAD"), \
                                 os.path.join(repo.path, "testfile"))
    >>> repo.is_clean()[0]
    False
    >>> repo.add_files(repo.path, force=True)
    >>> repo.commit_all(msg="foo")
    >>> repo.is_clean()[0]
    True
    >>> h = repo.head
    >>> len(h)
    40
    """


def test_branch_master():
    """
    First branch is called I{master}

    Methods tested:
         - L{gbp.git.GitRepository.get_branch}
    >>> import gbp.git, shutil
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> repo.get_branch()
    'master'
    >>> repo.branch
    'master'
    """


def test_create_branch():
    """
    Create a branch name I{foo}

    Methods tested:
         - L{gbp.git.GitRepository.create_branch}

    >>> import gbp.git, shutil
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> repo.create_branch("foo")
    """


def test_set_branch():
    """
    Switch to branch named I{foo}

    Methods tested:
         - L{gbp.git.GitRepository.set_branch}
         - L{gbp.git.GitRepository.get_branch}
         - L{gbp.git.GitRepository.branch}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> repo.set_branch("foo")
    >>> repo.get_branch() == "foo"
    True
    >>> repo.branch == "foo"
    True
    """


def test_tag():
    """
    Create a tag named I{tag}

    Methods tested:
         - L{gbp.git.GitRepository.create_tag}
         - L{gbp.git.GitRepository.has_tag}
         - L{gbp.git.GitRepository.get_tags}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> repo.create_tag("tag")
    >>> repo.has_tag("tag")
    True
    >>> repo.has_tag("unknown")
    False
    >>> repo.create_tag("tag2", msg="foo")
    >>> repo.has_tag("tag2")
    True
    >>> repo.get_tags()
    ['tag', 'tag2']
    >>> repo.tags
    ['tag', 'tag2']
    """


def test_move_tag():
    """
    Remove tags

    Methods tested:
         - L{gbp.git.GitRepository.move_tag}
         - L{gbp.git.GitRepository.has_tag}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> repo.move_tag("tag", "moved")
    >>> repo.has_tag("tag")
    False
    >>> repo.has_tag("moved")
    True
    """

def test_delete_tag():
    """
    Delete tags

    Methods tested:
         - L{gbp.git.GitRepository.delete_tag}
         - L{gbp.git.GitRepository.has_tag}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> repo.has_tag("moved")
    True
    >>> repo.delete_tag("moved")
    >>> repo.has_tag("moved")
    False
    """

def test_list_files():
    """
    List files in the index

    Methods tested:
         - L{gbp.git.GitRepository.list_files}
         - L{gbp.git.GitRepository.add_files}
         - L{gbp.git.GitRepository.commit_staged}
         - L{gbp.git.GitRepository.commit_files}
         - L{gbp.git.GitRepository.force_head}

    >>> import gbp.git, os, shutil
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> src = os.path.join(repo.path, ".git/HEAD")
    >>> dst = os.path.join(repo.path, "testfile")
    >>> repo.list_files()
    ['testfile']
    >>> repo.list_files(['modified'])
    []
    >>> repo.list_files(['modified', 'deleted'])
    []
    >>> repo.list_files(['modified', 'deleted', 'cached'])
    ['testfile']
    >>> shutil.copy(src, dst)
    >>> repo.list_files(['modified'])
    ['testfile']
    >>> repo.add_files(dst)
    >>> repo.commit_staged(msg="foo")
    >>> repo.list_files(['modified'])
    []
    >>> repo.list_files(['foo'])
    Traceback (most recent call last):
    ...
    GitRepositoryError: Unknown type 'foo'
    >>> repo.force_head('HEAD^', hard=True)
    >>> repo.list_files(['modified'])
    []
    >>> shutil.copy(src, dst)
    >>> repo.list_files(['modified'])
    ['testfile']
    >>> repo.commit_files(dst, msg="foo")
    >>> repo.list_files(['modified'])
    []
    """


def test_mirror_clone():
    """
    Mirror a repository

    Methods tested:
         - L{gbp.git.GitRepository.clone}
         - L{gbp.git.GitRepository.is_empty}
         - L{gbp.git.GitRepository.set_branch}
         - L{gbp.git.GitRepository.has_branch}
         - L{gbp.git.GitRepository.branch}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> repo.set_branch('master')
    >>> mirror = gbp.git.GitRepository.clone(mirror_clone_dir, repo.path, mirror=True)
    >>> mirror.is_empty()
    False
    >>> mirror.branch
    'master'
    >>> mirror.has_branch('foo')
    True
    >>> mirror.has_branch('bar')
    False
    >>> mirror.set_branch('foo')
    >>> mirror.branch
    'foo'
    >>> mirror.force_head('foo^')
    """

def test_clone():
    """
    Clone a repository

    Methods tested:
         - L{gbp.git.GitRepository.clone}
         - L{gbp.git.GitRepository.is_empty}
         - L{gbp.git.GitRepository.set_branch}
         - L{gbp.git.GitRepository.branch}
         - L{gbp.git.GitRepository.get_remote_branches}
         - L{gbp.git.GitRepository.get_local_branches}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> repo.set_branch('master')
    >>> clone = gbp.git.GitRepository.clone(clone_dir, repo.path)
    >>> clone.is_empty()
    False
    >>> clone.branch
    'master'
    >>> clone.get_remote_branches()
    ['origin/HEAD', 'origin/foo', 'origin/master']
    >>> clone.get_local_branches()
    ['master']
    >>> clone.get_merge_branch('master')
    'origin/master'
    >>> clone.create_branch('foo', 'origin/foo')
    >>> clone.get_merge_branch('foo')
    'origin/foo'
    >>> clone.get_local_branches()
    ['foo', 'master']
    """

def test_merge():
    """
    Merge a branch

    Methods tested:
         - L{gbp.git.GitRepository.merge}
         - L{gbp.git.GitRepository.set_branch}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> repo.set_branch('master')
    >>> repo.merge('foo')
    """

def test_pull():
    """
    Pull from a remote repository

    Methods tested:
         - L{gbp.git.GitRepository.set_branch}
         - L{gbp.git.GitRepository.pull}

    >>> import gbp.git, os
    >>> d = os.path.join(clone_dir, 'gbp_%s_test_repo' % __name__)
    >>> clone = gbp.git.GitRepository(d)
    >>> clone.set_branch('master')
    >>> clone.pull()
    """

def test_fetch():
    """
    Fetch from a remote repository

    Methods tested:
         - L{gbp.git.GitRepository.fetch}

    >>> import gbp.git, os
    >>> d = os.path.join(clone_dir, 'gbp_%s_test_repo' % __name__)
    >>> clone = gbp.git.GitRepository(d)
    >>> clone.fetch()
    """

def test_create_bare():
    """
    Create a bare repository

    Methods tested:
         - L{gbp.git.GitRepository.create}
         - L{gbp.git.GitRepository.is_empty}

    >>> import gbp.git
    >>> bare = gbp.git.GitRepository.create(bare_dir, bare=True, description="msg")
    >>> bare.path == bare_dir
    True
    >>> bare.git_dir[:-1] == bare_dir
    True
    >>> type(bare) == gbp.git.GitRepository
    True
    >>> bare.is_empty()
    True
    >>> bare.is_clean()
    (True, '')
    """

def test_checkout():
    """
    Checkout treeishs

    Methods tested:
         - L{gbp.git.GitRepository.checkout}
         - L{gbp.git.GitRepository.get_branch}
         - L{gbp.git.GitRepository.set_branch}
         - L{gbp.git.GitRepository.rev_parse}

    Properties tested:
         - L{gbp.git.GitRepository.branch}
         - L{gbp.git.GitRepository.tags}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(repo_dir)
    >>> repo.checkout('master')
    >>> repo.branch
    'master'
    >>> sha1 = repo.rev_parse('master')
    >>> repo.checkout(sha1)
    >>> repo.branch
    >>> repo.get_branch()
    Traceback (most recent call last):
    ...
    GitRepositoryError: Currently not on a branch
    >>> tag = repo.tags[0]
    >>> repo.checkout(tag)
    >>> repo.branch
    """

def test_teardown():
    """
    Perform the teardown

    >>> import shutil, os
    >>> os.getenv("GBP_TESTS_NOCLEAN") or shutil.rmtree(repo_dir)
    >>> os.getenv("GBP_TESTS_NOCLEAN") or shutil.rmtree(bare_dir)
    >>> os.getenv("GBP_TESTS_NOCLEAN") or shutil.rmtree(mirror_clone_dir)
    >>> os.getenv("GBP_TESTS_NOCLEAN") or shutil.rmtree(clone_dir)
    """

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
