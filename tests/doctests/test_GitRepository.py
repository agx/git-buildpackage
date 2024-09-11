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


def test_repo():
    """
    Create a repository

    Methods tested:
         - L{gbp.git.GitRepository.create}

    Properties tested:
         - L{gbp.git.GitRepository.path}
         - L{gbp.git.GitRepository.git_dir}

    >>> setup_module()
    >>> import shutil, os, gbp.git
    >>> repo = gbp.git.GitRepository.create(dirs['repo'])
    >>> repo.path == dirs['repo']
    True
    >>> repo.git_dir == os.path.join(dirs['repo'], '.git')
    True
    >>> type(repo) == gbp.git.GitRepository
    True
    >>> # test_empty()
    >>> # Empty repos have no branch
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.get_branch()
    >>> repo.branch
    >>> repo.is_empty()
    True
    >>> # test_subdir()
    >>> # Make sure we can init repos from a subdir
    >>> os.mkdir(os.path.join(dirs['repo'], 'subdir'))
    >>> repo = gbp.git.GitRepository(os.path.join(dirs['repo'], 'subdir'), toplevel=False)
    >>> repo.path == dirs['repo']
    True
    >>> repo = gbp.git.GitRepository(os.path.join(dirs['repo'], 'subdir'), toplevel=True) # doctest:+ELLIPSIS
    Traceback (most recent call last):
    ...
    gbp.git.repository.GitRepositoryError: Not the toplevel of a Git repository at ...
    >>> # test_add_files:
    >>> # Add some dummy data
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
    >>> # test_rename_file:
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.rename_file("testfile", "testfile2")
    >>> repo.rename_file("testfile2", "testfile")
    >>> repo.rename_file("doesnotexit", "testfile2")
    Traceback (most recent call last):
    ...
    gbp.errors.GbpError: Failed to move 'doesnotexit' to 'testfile2': fatal: bad source, source=doesnotexit, destination=testfile2
    >>> # test_branch_master:
    >>> # First branch is called I{master}
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.get_branch()
    'master'
    >>> repo.branch
    'master'
    >>> # test_clean:
    >>> # Remove untracked files from the working tree
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> ret = shutil.copy(os.path.join(repo.path, ".git/HEAD"),
    ...                                os.path.join(repo.path, "testclean"))
    >>> repo.clean(dry_run=True)
    >>> repo.is_clean()[0]
    False
    >>> repo.clean(directories=True, force=True)
    >>> repo.is_clean()[0]
    True
    >>> # test_create_branch:
    >>> # Create a branch name I{foo}
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.create_branch("foo")
    >>> repo.branch_contains("foo", 'HEAD')
    True
    >>> repo.branch_contains("doesnotexist", 'HEAD', remote=True)
    False
    >>> # test_delete_branch:
    >>> # Create a branch named I{foo2} and delete it
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.create_branch("bar")
    >>> repo.delete_branch("bar")
    >>> repo.delete_branch("master")
    Traceback (most recent call last):
    ...
    gbp.git.repository.GitRepositoryError: Can't delete the branch you're on
    >>> # test_set_branch:
    >>> # Switch to branch named I{foo}
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.set_branch("foo")
    >>> repo.get_branch() == "foo"
    True
    >>> repo.branch == "foo"
    True
    >>> # test_rename_branch:
    >>> # Create branch named I{baz}, rename it to I{bax} and finally delete it
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.create_branch("baz")
    >>> repo.rename_branch("baz", "bax")
    >>> repo.delete_branch("bax")
    >>> # test_set_upstream_branch
    >>> # Set upstream branch master -> origin/master
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
    gbp.git.repository.GitRepositoryError: Branch bla doesn't exist!
    >>> repo.set_upstream_branch('foo', 'origin/bla')
    Traceback (most recent call last):
    gbp.git.repository.GitRepositoryError: Branch origin/bla doesn't exist!
    >>> # test_get_upstream_branch():
    >>> # Get info about upstream branches set in test_set_upstream_branch
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.get_upstream_branch('master')
    'origin/master'
    >>> repo.get_upstream_branch('foo')
    ''
    >>> repo.get_upstream_branch('bla')
    Traceback (most recent call last):
    gbp.git.repository.GitRepositoryError: Branch bla doesn't exist!
    >>> # test_tag():
    >>> # Create a tag named I{tag} and check its existence
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
    >>> # test_describe():
    >>> # Describe commit-ish
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> sha = repo.rev_parse('HEAD')
    >>> repo.describe('HEAD')
    'tag2'
    >>> repo.describe('HEAD', longfmt=True) == 'tag2-0-g%s' % sha[:7]
    True
    >>> repo.describe('HEAD', pattern='foo*')
    Traceback (most recent call last):
    ...
    gbp.git.repository.GitRepositoryError: Can't describe HEAD. Git error: fatal: No names found, cannot describe anything.
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
    >>> # test_find_tag():
    >>> # Find tags
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.find_tag('HEAD')
    'tag2'
    >>> repo.find_tag('HEAD', pattern='foo*')
    Traceback (most recent call last):
    ...
    gbp.git.repository.GitRepositoryError: Can't describe HEAD. Git error: fatal: No names found, cannot describe anything.
    >>> # test_find_branch_tag():
    >>> # Find the closest tags on a certain branch to a given commit
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.find_branch_tag('HEAD', 'master', 'tag*')
    'tag2'
    >>> repo.find_branch_tag('HEAD', 'master', 'v*')   # doctest:+ELLIPSIS
    Traceback (most recent call last):
    ...
    gbp.git.repository.GitRepositoryError: Can't describe .... Git error: fatal: No names found, cannot describe anything.
    >>> # test_move_tag():
    >>> # Move a tag
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.move_tag("tag", "moved")
    >>> repo.has_tag("tag")
    False
    >>> repo.has_tag("moved")
    True
    >>> # test_delete_tag():
    >>> # Delete tags
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.has_tag("moved")
    True
    >>> repo.delete_tag("moved")
    >>> repo.has_tag("moved")
    False
    >>> # test_get_obj_type():
    >>> # Find commit SHA1 related to tags
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.create_tag("tag3", "tag msg")
    >>> repo.get_obj_type("tag3")
    'tag'
    >>> repo.get_obj_type("HEAD")
    'commit'
    >>> repo.get_obj_type("HEAD:testfile")
    'blob'
    >>> repo.delete_tag("tag3")
    >>> # test_list_files():
    >>> # List files in the index
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> src = os.path.join(repo.path, ".git/HEAD")
    >>> dst = os.path.join(repo.path, "testfile")
    >>> repo.list_files()
    [b'testfile']
    >>> repo.list_files(['modified'])
    []
    >>> repo.list_files(['modified', 'deleted'])
    []
    >>> repo.list_files(['modified', 'deleted', 'cached'])
    [b'testfile']
    >>> ret = shutil.copy(src, dst)
    >>> repo.list_files(['modified'])
    [b'testfile']
    >>> repo.add_files(dst)
    >>> repo.commit_staged(msg="foo")
    >>> repo.list_files(['modified'])
    []
    >>> repo.list_files(['foo'])
    Traceback (most recent call last):
    ...
    gbp.git.repository.GitRepositoryError: Unknown type 'foo'
    >>> repo.force_head('HEAD^', hard=True)
    >>> repo.list_files(['modified'])
    []
    >>> ret = shutil.copy(src, dst)
    >>> repo.list_files(['modified'])
    [b'testfile']
    >>> repo.commit_files(dst, msg="foo")
    >>> repo.list_files(['modified'])
    []
    >>> # test_get_commits():
    >>> # Test listing commits
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
    >>> # test_get_commit_info():
    >>> # Test inspecting commits
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
    defaultdict(<class 'list'>, {'M': [b'testfile']})
    >>> repo.get_subject('HEAD')
    'foo'
    >>> # test_diff():
    >>> # Test git-diff
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
    >>> # test_diff_status():
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.diff_status("HEAD", "HEAD")
    defaultdict(<class 'list'>, {})
    >>> repo.diff_status("HEAD~1", "HEAD")
    defaultdict(<class 'list'>, {'M': [b'testfile']})
    >>> # test_mirror_clone():
    >>> # Mirror a repository
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.set_branch('master')
    >>> repo.branch
    'master'
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
    >>> # test_clone():
    >>> # Clone a repository
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.set_branch('master')
    >>> clone = gbp.git.GitRepository.clone(dirs['clone'], repo.path)
    >>> clone.is_empty()
    False
    >>> clone.branch
    'master'
    >>> clone.get_remote_branches()
    ['origin', 'origin/foo', 'origin/master']
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
    >>> # test_get_remotes():
    >>> # Check remotes
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
    >>> # test_merge():
    >>> # Merge a branch
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.set_branch('master')
    >>> repo.merge('foo')
    >>> repo.is_in_merge()
    False
    >>> # test_pull():
    >>> # Pull from a remote repository
    >>> d = os.path.join(dirs['clone'], 'repo')
    >>> clone = gbp.git.GitRepository(d)
    >>> clone.set_branch('master')
    >>> clone.pull()
    >>> clone.pull(all_remotes=True)
    >>> clone.pull('origin', all_remotes=True)
    >>> # test_fetch():
    >>> # Fetch from a remote repository
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
    >>> # test_create_bare():
    >>> # Create a bare repository
    >>> bare = gbp.git.GitRepository.create(dirs['bare'], bare=True, description="msg")
    >>> bare.path == dirs['bare']
    True
    >>> bare.git_dir == dirs['bare']
    True
    >>> type(bare) == gbp.git.GitRepository
    True
    >>> bare.is_empty()
    True
    >>> bare.is_clean()
    (True, '')
    >>> # test_nonexistent():
    >>> # Check that accessing a non-existent repository fails.
    >>> bare = gbp.git.GitRepository("/does/not/exist")
    Traceback (most recent call last):
    ...
    gbp.git.repository.GitRepositoryError: No Git repository at '/does/not/exist'
    >>> # test_create_noperm():
    >>> # Check that creating a repository at a path that isn't writeable fails
    >>> gbp.git.GitRepository.create("/does/not/exist")
    Traceback (most recent call last):
    ...
    gbp.git.repository.GitRepositoryError: Cannot create Git repository at '/does/not/exist': [Errno 13] Permission denied: '/does'
    >>> # test_checkout():
    >>> # Checkout treeishs
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.checkout('master')
    >>> repo.branch
    'master'
    >>> repo.rev_parse('doesnotexist')
    Traceback (most recent call last):
    ...
    gbp.git.repository.GitRepositoryError: revision 'doesnotexist' not found
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
    gbp.git.repository.GitRepositoryError: Currently not on a branch
    >>> tag = repo.tags[0]
    >>> repo.checkout(tag)
    >>> repo.branch
    >>> # test_gc():
    >>> # Test garbage collection
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.collect_garbage()
    >>> repo.collect_garbage(prune=True)
    >>> repo.collect_garbage(prune='all', aggressive=True)
    >>> # test_grep_log():
    >>> # Test grepping through commit messages
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
    gbp.git.repository.GitRepositoryError: Error grepping log for foo: fatal: bad revision 'doesnotexist'
    >>> # test_is_ff():
    >>> # Test if branch is fast forwardable
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.is_fast_forward('master', 'foo')
    (True, True)
    >>> repo.create_branch('ff', 'HEAD^')
    >>> repo.is_fast_forward('ff', 'master')
    (True, False)
    >>> repo.is_fast_forward('master', 'ff')
    (False, True)
    >>> # test_update_ref():
    >>> # Test updating a reference
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.update_ref('new_ref', 'master', msg='update')
    >>> os.path.exists(os.path.join(repo.git_dir, 'new_ref'))
    True
    >>> # test_make_tree():
    >>> # Test git-mk-tree
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> sha1 = repo.write_file('testfile')
    >>> sha1
    '19af7398c894bc5e86e17259317e4db519e9241f'
    >>> head = list(repo.list_tree('HEAD'))
    >>> head
    [('100644', 'blob', '19af7398c894bc5e86e17259317e4db519e9241f', b'testfile')]
    >>> head.append(['100644', 'blob', '19af7398c894bc5e86e17259317e4db519e9241f', 'testfile2'])
    >>> newtree = repo.make_tree(head)
    >>> newtree
    '745951810c9e22fcc6de9b23f05efd6ab5512123'
    >>> list(repo.list_tree(newtree, recurse=False, paths='testfile'))
    [('100644', 'blob', '19af7398c894bc5e86e17259317e4db519e9241f', b'testfile')]
    >>> list(repo.list_tree(newtree, recurse=False, paths='testfile', sizes=True))
    [('100644', 'blob', '19af7398c894bc5e86e17259317e4db519e9241f', 20, b'testfile')]
    >>> repo.make_tree([])
    '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
    >>> # test_update_submodules():
    >>> # Updating submodules if we don't have any is a noop
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.has_submodules()
    False
    >>> repo.update_submodules()
    >>> # test_get_merge_base():
    >>> # Find the common ancestor of two objects
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> sha1 = repo.get_merge_base('master', 'foo')
    >>> len(sha1)
    40
    >>> repo.get_merge_base('master', 'doesnotexist')
    Traceback (most recent call last):
    ...
    gbp.git.repository.GitRepositoryError: Failed to get common ancestor: fatal: Not a valid object name doesnotexist
    >>> # test_status():
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> fname = os.path.join(repo.path, "test_status")
    >>> ret = shutil.copy(os.path.join(repo.path, ".git/HEAD"), fname)
    >>> list(repo.status().items())
    [('??', [b'test_status'])]
    >>> list(repo.status(['bla*']).items())
    []
    >>> list(repo.status(['te*']).items())
    [('??', [b'test_status'])]
    >>> repo.add_files(repo.path, force=True)
    >>> repo.commit_all(msg='added %s' % fname)
    >>> _ = repo._git_inout('mv', [fname, fname + 'new'])
    >>> list(repo.status().items())
    [('R ', [b'test_status\\x00test_statusnew'])]
    >>> # test_cmd_has_feature():
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
    gbp.git.repository.GitRepositoryError: Invalid git command 'foobarcmd': No manual entry for gitfoobarcmd
    >>> repo._cmd_has_feature("show", "standard-notes")
    True
    >>> repo._cmd_has_feature("show", "no-standard-notes")
    True
    >>> # test_set_user_name_and_email():
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.set_user_name("Michael Stapelberg")
    >>> repo.set_user_email("stapelberg@test.invalid")
    >>> # test_set_config_and_get_config():
    >>> repo = gbp.git.GitRepository(dirs['repo'])
    >>> repo.set_config("user.email", "foo@example.com")
    >>> repo.get_config("user.email")
    'foo@example.com'
    >>> # test_git_dir():
    >>> git_dir = os.path.join(dirs['repo'], '.git')
    >>> os.environ['GIT_DIR'] = git_dir
    >>> somewhere = gbp.git.GitRepository(os.path.join(dirs['repo'], '..'))
    >>> somewhere.git_dir == git_dir
    True
    >>> del os.environ['GIT_DIR']
    >>> teardown_module()
    """

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
