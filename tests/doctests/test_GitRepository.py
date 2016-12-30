# vim: set fileencoding=utf-8 :

"""
Test L{gbp.git.GitRepository}

This testcase creates several repositores:

    - A repository at I{dirs['repo']} called I{repo}
    - A bare repository at I{dirs['bare']} called I{bare}
    - A clone of I{repo} below I{dirs['clone']} called I{clone}
    - A mirror of I{repo} below I{mirror_dirs['clone']} called I{mirror}
"""

from .. import context

import gbp.log

gbp.log.setup(color=False, verbose=True)

dirs = {}
subdirs = ['repo', 'bare', 'clone', 'mirror_clone']


def setup_module():
    tmpdir = context.new_tmpdir(__name__)
    for s in subdirs:
        dirs[s] = tmpdir.join(s)


def teardown_module():
    for s in subdirs:
        del dirs[s]
    context.teardown()


def test_create():
    """
    Create a repository

    Methods tested:
         - L{gbp.git.GitRepository.create}

    Properties tested:
         - L{gbp.git.GitRepository.path}
         - L{gbp.git.GitRepository.git_dir}

    >>> import os, gbp.git
    >>> repo = gbp.git.GitRepository.create(dirs['repo'])
    >>> repo.path == dirs['repo']
    True
    >>> repo.git_dir == os.path.join(dirs['repo'], '.git')
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
    >>> repo = gbp.git.GitRepository(dirs['repo'])
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

    >>> import gbp.git, shutil, os
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> ret = shutil.copy(os.path.join(repo.path, ".git/HEAD"),
    ...                                os.path.join(repo.path, "testfile"))
    >>> repo.is_clean()[0]
    False
    >>> repo.is_clean('doesnotexist')[0]
    True
    >>> repo.is_clean(paths='testfile')[0]
    False
    >>> repo.is_clean(paths=['doesnotexist', 'testfile'])[0]
    False
    >>> repo.is_clean(ignore_untracked=True)[0]
    True
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
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.get_branch()
    'master'
    >>> repo.branch
    'master'
    """


def test_clean():
    """
    Remove untracked files from the working tree

    Methods tested:
         - L{gbp.git.GitRepository.clean}

    >>> import gbp.git, shutil, os
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> ret = shutil.copy(os.path.join(repo.path, ".git/HEAD"),
    ...                                os.path.join(repo.path, "testclean"))
    >>> repo.clean(dry_run=True)
    >>> repo.is_clean()[0]
    False
    >>> repo.clean(directories=True, force=True)
    >>> repo.is_clean()[0]
    True
    """


def test_create_branch():
    """
    Create a branch name I{foo}

    Methods tested:
         - L{gbp.git.GitRepository.create_branch}
         - L{gbp.git.GitRepository.branch_contains}

    >>> import gbp.git, shutil
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.create_branch("foo")
    >>> repo.branch_contains("foo", 'HEAD')
    True
    >>> repo.branch_contains("doesnotexist", 'HEAD', remote=True)
    False
    """


def test_delete_branch():
    """
    Create a branch named I{foo2} and delete it

    Methods tested:
         - L{gbp.git.GitRepository.create_branch}
         - L{gbp.git.GitRepository.delete_branch}

    >>> import gbp.git, shutil
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.create_branch("bar")
    >>> repo.delete_branch("bar")
    >>> repo.delete_branch("master")
    Traceback (most recent call last):
    ...
    GitRepositoryError: Can't delete the branch you're on
    """


def test_set_branch():
    """
    Switch to branch named I{foo}

    Methods tested:
         - L{gbp.git.GitRepository.set_branch}
         - L{gbp.git.GitRepository.get_branch}
         - L{gbp.git.GitRepository.branch}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.set_branch("foo")
    >>> repo.get_branch() == "foo"
    True
    >>> repo.branch == "foo"
    True
    """


def test_rename_branch():
    """
    Create branch named I{baz}, rename it to I{bax} and finally delete it

    Methods tested:
         - L{gbp.git.GitRepository.create_branch}
         - L{gbp.git.GitRepository.rename_branch}
         - L{gbp.git.GitRepository.delete_branch}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.create_branch("baz")
    >>> repo.rename_branch("baz", "bax")
    >>> repo.delete_branch("bax")
    """


def test_set_upstream_branch():
    """
    Set upstream branch master -> origin/master

    >>> import os, shutil
    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> os.makedirs(os.path.join(repo.git_dir, 'refs/remotes/origin'))
    >>> ret = shutil.copy(os.path.join(repo.git_dir, 'refs/heads/master'), \
                    os.path.join(repo.git_dir, 'refs/remotes/origin/'))
    >>> repo.add_remote_repo('origin', 'git://git.example.com/git/origin')
    >>> repo.set_upstream_branch('master', 'origin/master')
    >>> repo.get_upstream_branch('master')
    'origin/master'
    >>> repo.set_upstream_branch('bla', 'origin/master')
    Traceback (most recent call last):
    GitRepositoryError: Branch bla doesn't exist!
    >>> repo.set_upstream_branch('foo', 'origin/bla')
    Traceback (most recent call last):
    GitRepositoryError: Branch origin/bla doesn't exist!
    """


def test_get_upstream_branch():
    """
    Get info about upstream branches set in test_set_upstream_branch

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.get_upstream_branch('master')
    'origin/master'
    >>> repo.get_upstream_branch('foo')
    ''
    >>> repo.get_upstream_branch('bla')
    Traceback (most recent call last):
    GitRepositoryError: Branch bla doesn't exist!
    """


def test_tag():
    """
    Create a tag named I{tag} and check its existance

    Methods tested:
         - L{gbp.git.GitRepository.create_tag}
         - L{gbp.git.GitRepository.verify_tag}
         - L{gbp.git.GitRepository.has_tag}
         - L{gbp.git.GitRepository.get_tags}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.create_tag("tag")
    >>> repo.has_tag("tag")
    True
    >>> repo.has_tag("unknown")
    False
    >>> repo.create_tag("tag2", msg="foo")
    >>> repo.has_tag("tag2")
    True
    >>> repo.verify_tag("tag2")
    False
    >>> repo.get_tags()
    ['tag', 'tag2']
    >>> repo.tags
    ['tag', 'tag2']
    """


def test_describe():
    """
    Describe commit-ish

    Methods tested:
         - L{gbp.git.GitRepository.describe}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> sha = repo.rev_parse('HEAD')
    >>> repo.describe('HEAD')
    'tag2'
    >>> repo.describe('HEAD', longfmt=True) == 'tag2-0-g%s' % sha[:7]
    True
    >>> repo.describe('HEAD', pattern='foo*')
    Traceback (most recent call last):
    ...
    GitRepositoryError: Can't describe HEAD. Git error: fatal: No names found, cannot describe anything.
    >>> repo.describe('HEAD', pattern='foo*', always=True) == sha[:7]
    True
    >>> repo.describe('HEAD', always=True, abbrev=16)
    'tag2'
    >>> repo.describe('HEAD', pattern='foo*', always=True, abbrev=16) == sha[:16]
    True
    >>> tag = repo.describe('HEAD', longfmt=True, abbrev=16) == 'tag2-0-g%s' % sha[:16]
    >>> repo.delete_tag('tag2')
    >>> repo.describe('HEAD', tags=True)
    'tag'
    >>> repo.describe('HEAD', tags=True, exact_match=True)
    'tag'
    >>> repo.create_tag('tag2', msg='foo')
    """


def test_find_tag():
    """
    Find tags

    Methods tested:
         - L{gbp.git.GitRepository.find_tag}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.find_tag('HEAD')
    'tag2'
    >>> repo.find_tag('HEAD', pattern='foo*')
    Traceback (most recent call last):
    ...
    GitRepositoryError: Can't describe HEAD. Git error: fatal: No names found, cannot describe anything.
    """


def test_find_branch_tag():
    """
    Find the closest tags on a certain branch to a given commit

    Methods tested:
         - L{gbp.git.GitRepository.find_branch_tag}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.find_branch_tag('HEAD', 'master', 'tag*')
    'tag2'
    >>> repo.find_branch_tag('HEAD', 'master', 'v*')   # doctest:+ELLIPSIS
    Traceback (most recent call last):
    ...
    GitRepositoryError: Can't describe .... Git error: fatal: No names found, cannot describe anything.
    """


def test_move_tag():
    """
    Move a tag

    Methods tested:
         - L{gbp.git.GitRepository.move_tag}
         - L{gbp.git.GitRepository.has_tag}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
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
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.has_tag("moved")
    True
    >>> repo.delete_tag("moved")
    >>> repo.has_tag("moved")
    False
    """


def test_get_obj_type():
    """
    Find commit SHA1 related to tags

    Methods tested:
         - L{gbp.git.GitRepository.create_tag}
         - L{gbp.git.GitRepository.get_obj_type}
         - L{gbp.git.GitRepository.delete_tag}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.create_tag("tag3", "tag msg")
    >>> repo.get_obj_type("tag3")
    'tag'
    >>> repo.get_obj_type("HEAD")
    'commit'
    >>> repo.get_obj_type("HEAD:testfile")
    'blob'
    >>> repo.delete_tag("tag3")
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
    >>> repo = gbp.git.GitRepository(dirs['repo'])
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
    >>> ret = shutil.copy(src, dst)
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
    >>> ret = shutil.copy(src, dst)
    >>> repo.list_files(['modified'])
    ['testfile']
    >>> repo.commit_files(dst, msg="foo")
    >>> repo.list_files(['modified'])
    []
    """


def test_get_commits():
    """
    Test listing commits

    Methods tested:
         - L{gbp.git.GitRepository.get_commits}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> commits = repo.get_commits()
    >>> type(commits) == list and len(commits) == 2
    True
    >>> len(repo.get_commits(num=1)) == 1
    True
    >>> commits2 = repo.get_commits(since='HEAD~1')
    >>> len(commits2) == 1
    True
    >>> commits2[0] == commits[0]
    True
    >>> commits2 = repo.get_commits(until='HEAD~1')
    >>> len(commits2) == 1
    True
    >>> commits2[0] == commits[-1]
    True
    >>> repo.get_commits(paths=['foo', 'bar'])
    []
    >>> repo.get_commits(paths=['testfile']) == commits
    True
    """


def test_get_commit_info():
    """
    Test inspecting commits

    Methods tested:
         - L{gbp.git.GitRepository.get_commit_info}

    >>> import gbp.git
    >>> from datetime import datetime
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> info = repo.get_commit_info('HEAD')
    >>> info['id']
    'HEAD'
    >>> info['body']
    ''
    >>> info['subject']
    'foo'
    >>> '@' in info['author'].email
    True
    >>> '@' in info['committer'].email
    True
    >>> now = datetime.now()
    >>> (now - datetime.fromtimestamp(int(info['author'].date.split()[0]))).seconds < 10
    True
    >>> (now - datetime.fromtimestamp(int(info['committer'].date.split()[0]))).seconds < 10
    True
    >>> info['patchname']
    'foo'
    >>> info['files']                               # doctest:+ELLIPSIS
    defaultdict(<... 'list'>, {'M': ['testfile']})
    >>> repo.get_subject('HEAD')
    'foo'
    """


def test_diff():
    """
    Test git-diff

    Methods tested:
         - L{gbp.git.GitRepository.diff}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> len(repo.diff('HEAD~1', 'HEAD')) > 3
    True
    >>> len(repo.diff('HEAD~1', 'HEAD', 'testfile')) > 3
    True
    >>> len(repo.diff('HEAD~1', 'HEAD', 'testfile', text=True)) > 3
    True
    >>> len(repo.diff('HEAD~1', 'HEAD', 'filenotexist')) == 0
    True
    >>> repo.diff('HEAD~1', 'HEAD') == repo.diff('HEAD~1')
    True
    """


def test_diff_status():
    """
    Methods tested:
        - L{gbp.git.GitRepository.diff_status}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.diff_status("HEAD", "HEAD")            # doctest:+ELLIPSIS
    defaultdict(<... 'list'>, {})
    >>> repo.diff_status("HEAD~1", "HEAD")          # doctest:+ELLIPSIS
    defaultdict(<... 'list'>, {'M': ['testfile']})
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
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.set_branch('master')
    >>> mirror = gbp.git.GitRepository.clone(dirs['mirror_clone'], repo.path, mirror=True)
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
         - L{gbp.git.GitRepository.get_merge_branch}
         - L{gbp.git.GitRepository.get_remote_branches}
         - L{gbp.git.GitRepository.get_local_branches}
         - L{gbp.git.GitRepository.get_remote_repos}
         - L{gbp.git.GitRepository.has_remote_repo}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.set_branch('master')
    >>> clone = gbp.git.GitRepository.clone(dirs['clone'], repo.path)
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
    >>> clone.create_branch('bar')
    >>> clone.get_merge_branch('bar') # None if no merge branch exists
    >>> clone.get_local_branches()
    ['bar', 'foo', 'master']
    >>> clone.get_remote_repos()
    ['origin']
    >>> clone.has_remote_repo('origin')
    True
    >>> clone.has_branch('origin/master', remote=True)
    True
    >>> clone.has_remote_repo('godiug')
    False
    """


def test_get_remotes():
    """
    Merge a branch

    Methods tested:
         - L{gbp.git.GitRepository.get_remotes}

    >>> import os
    >>> import gbp.git.repository
    >>> repo = gbp.git.repository.GitRepository(os.path.join(dirs['clone'], 'repo'))
    >>> remotes = repo.get_remotes()
    >>> len(remotes)
    1
    >>> origin = remotes['origin']
    >>> origin.name
    'origin'
    >>> origin.fetch_url == dirs['repo']
    True
    >>> origin.push_urls == [dirs['repo']]
    True
    """


def test_merge():
    """
    Merge a branch

    Methods tested:
         - L{gbp.git.GitRepository.merge}
         - L{gbp.git.GitRepository.set_branch}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
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
    >>> d = os.path.join(dirs['clone'], 'repo')
    >>> clone = gbp.git.GitRepository(d)
    >>> clone.set_branch('master')
    >>> clone.pull()
    >>> clone.pull(all_remotes=True)
    >>> clone.pull('origin', all_remotes=True)
    """


def test_fetch():
    """
    Fetch from a remote repository

    Methods tested:
         - L{gbp.git.GitRepository.fetch}
         - L{gbp.git.GitRepository.push}
         - L{gbp.git.GitRepository.push_tag}
         - L{gbp.git.GitRepository.add_remote_repo}
         - L{gbp.git.GitRepository.remove_remote_repo}

    >>> import gbp.git, os
    >>> d = os.path.join(dirs['clone'], 'repo')
    >>> clone = gbp.git.GitRepository(d)
    >>> clone.fetch()
    >>> clone.push()
    >>> clone.push('origin', dry_run=True)
    >>> clone.push('origin')
    >>> clone.push('origin', 'master')
    >>> clone.push('origin', 'master', force=True)
    >>> clone.create_tag('tag3')
    >>> clone.push_tag('origin', 'tag3', True)
    >>> clone.push_tag('origin', 'tag3')
    >>> clone.create_tag('tag4')
    >>> clone.push('origin', 'master', tags=True)
    >>> clone.add_remote_repo('foo', dirs['repo'])
    >>> clone.fetch('foo')
    >>> clone.fetch('foo', tags=True)
    >>> clone.fetch('foo', refspec='refs/heads/master')
    >>> clone.fetch(all_remotes=True)
    >>> clone.remove_remote_repo('foo')
    """


def test_create_bare():
    """
    Create a bare repository

    Methods tested:
         - L{gbp.git.GitRepository.create}
         - L{gbp.git.GitRepository.is_empty}

    >>> import gbp.git
    >>> bare = gbp.git.GitRepository.create(dirs['bare'], bare=True, description="msg")
    >>> bare.path == dirs['bare']
    True
    >>> bare.git_dir[:-1] == dirs['bare']
    True
    >>> type(bare) == gbp.git.GitRepository
    True
    >>> bare.is_empty()
    True
    >>> bare.is_clean()
    (True, '')
    """


def test_nonexistent():
    """
    Check that accessing a non-existent repository fails.

    Methods tested:
         - L{gbp.git.GitRepository.__init__}

    >>> import gbp.git
    >>> bare = gbp.git.GitRepository("/does/not/exist")
    Traceback (most recent call last):
    ...
    GitRepositoryError: No Git repository at '/does/not/exist'
    """


def test_create_noperm():
    """
    Check that creating a repository at a path that isn't writeable fails

    Methods tested:
         - L{gbp.git.GitRepository.create}

    >>> import gbp.git
    >>> gbp.git.GitRepository.create("/does/not/exist")
    Traceback (most recent call last):
    ...
    GitRepositoryError: Cannot create Git repository at '/does/not/exist': Permission denied
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
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.checkout('master')
    >>> repo.branch
    'master'
    >>> repo.rev_parse('doesnotexist')
    Traceback (most recent call last):
    ...
    GitRepositoryError: revision 'doesnotexist' not found
    >>> sha1 = repo.rev_parse('master', short=10)
    >>> len(sha1)
    10
    >>> sha1 = repo.rev_parse('master')
    >>> len(sha1)
    40
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


def test_gc():
    """
    Test garbace collection

    Methods tested:
         - L{gbp.git.GitRepository.collect_garbage}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.collect_garbage()
    """


def test_grep_log():
    """
    Test grepping through commit messages

    Methods tested:
        - L{gbp.git.GitRepository.grep_log}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.set_branch('master')
    >>> len(repo.grep_log('foo')) == 2
    True
    >>> len(repo.grep_log('foo', 'master')) == 2
    True
    >>> repo.grep_log('blafasel')
    []
    >>> repo.grep_log('foo', 'doesnotexist')
    Traceback (most recent call last):
    ...
    GitRepositoryError: Error grepping log for foo: fatal: bad revision 'doesnotexist'
    """


def test_is_ff():
    """
    Test if branch is fast forwardable

    Methods tested:
        - L{gbp.git.GitRepository.is_fast_forward}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.is_fast_forward('master', 'foo')
    (True, True)
    >>> repo.create_branch('ff', 'HEAD^')
    >>> repo.is_fast_forward('ff', 'master')
    (True, False)
    >>> repo.is_fast_forward('master', 'ff')
    (False, True)
    """


def test_update_ref():
    """
    Test updating a reference

    Methods tested:
        - L{gbp.git.GitRepository.update_ref}

    >>> import gbp.git, os
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.update_ref('new_ref', 'master', msg='update')
    >>> os.path.exists(os.path.join(repo.git_dir, 'new_ref'))
    True
    """


def test_make_tree():
    """
    Test git-mk-tree

    Methods tested:
        - L{gbp.git.GitRepository.write_file}
        - L{gbp.git.GitRepository.list_tree}
        - L{gbp.git.GitRepository.make_tree}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> sha1 = repo.write_file('testfile')
    >>> sha1
    '19af7398c894bc5e86e17259317e4db519e9241f'
    >>> head = repo.list_tree('HEAD')
    >>> head
    [['100644', 'blob', '19af7398c894bc5e86e17259317e4db519e9241f', 'testfile']]
    >>> head.append(['100644', 'blob', '19af7398c894bc5e86e17259317e4db519e9241f', 'testfile2'])
    >>> newtree = repo.make_tree(head)
    >>> newtree
    '745951810c9e22fcc6de9b23f05efd6ab5512123'
    >>> repo.list_tree(newtree, recurse=False, paths='testfile')
    [['100644', 'blob', '19af7398c894bc5e86e17259317e4db519e9241f', 'testfile']]
    """


def test_update_submodules():
    """
    Updating submodules if we don't have any is a noop

    Methods tested:
        - L{gbp.git.GitRepository.has_submodules}
        - L{gbp.git.GitRepository.update_submodules}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.has_submodules()
    False
    >>> repo.update_submodules()
    """


def test_get_merge_base():
    """
    Find the common ancestor of two objects

    Methods tested:
        - L{gbp.git.GitRepository.get_merge_base}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> sha1 = repo.get_merge_base('master', 'foo')
    >>> len(sha1)
    40
    >>> repo.get_merge_base('master', 'doesnotexist')
    Traceback (most recent call last):
    ...
    GitRepositoryError: Failed to get common ancestor: fatal: Not a valid object name doesnotexist
    """


def test_status():
    r"""
    Methods tested:
        - L{gbp.git.GitRepository.status}

    >>> import gbp.git, os, shutil
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> fname = os.path.join(repo.path, "test_status")
    >>> ret = shutil.copy(os.path.join(repo.path, ".git/HEAD"), fname)
    >>> list(repo.status().items())
    [('??', ['test_status'])]
    >>> list(repo.status(['bla*']).items())
    []
    >>> list(repo.status(['te*']).items())
    [('??', ['test_status'])]
    >>> repo.add_files(repo.path, force=True)
    >>> repo.commit_all(msg='added %s' % fname)
    >>> _ = repo._git_inout('mv', [fname, fname + 'new'])
    >>> list(repo.status().items())
    [('R ', ['test_status\x00test_statusnew'])]
    """


def test_cmd_has_feature():
    r"""
    Methods tested:
        - L{gbp.git.GitRepository._cmd_has_feature}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo._cmd_has_feature("commit", "a")
    True
    >>> repo._cmd_has_feature("commit", "reuse-message")
    True
    >>> repo._cmd_has_feature("merge", "n")
    True
    >>> repo._cmd_has_feature("merge", "stat")
    True
    >>> repo._cmd_has_feature("format-patch", "cc")
    True
    >>> repo._cmd_has_feature("merge", "foobaroption")
    False
    >>> repo._cmd_has_feature("foobarcmd", "foobaroption")
    Traceback (most recent call last):
    ...
    GitRepositoryError: Invalid git command 'foobarcmd': No manual entry for gitfoobarcmd
    >>> repo._cmd_has_feature("show", "standard-notes")
    True
    >>> repo._cmd_has_feature("show", "no-standard-notes")
    True
    """


def test_set_user_name_and_email():
    r"""
    Methods tested:
        - L{gbp.git.GitRepository.set_user_name}
        - L{gbp.git.GitRepository.set_user_email}

    >>> import gbp.git
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.set_user_name("Michael Stapelberg")
    >>> repo.set_user_email("stapelberg@test.invalid")
    """

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
