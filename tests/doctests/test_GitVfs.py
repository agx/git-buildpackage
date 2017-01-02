# vim: set fileencoding=utf-8 :

"""
Test L{gbp.git.GitVfs}
"""

import os
import gbp.log

from .. import context  # noqa: F401

gbp.log.setup(color=False, verbose=True)


def setup_repo():
    repo_dir = context.new_tmpdir(__name__)
    repo = gbp.git.GitRepository.create(str(repo_dir))
    content = 'al pha\na\nb\nc'
    with open(os.path.join(repo.path, 'foo.txt'), 'w') as f:
        f.write(content)
    repo.add_files(repo.path, force=True)
    repo.commit_all(msg="foo")
    return (repo, content)


def test_read():
    """
    Create a repository

    Methods tested:
         - L{gbp.git.GitVfs.open}
         - L{gbp.git.GitVfs._File.readline}
         - L{gbp.git.GitVfs._File.readlines}
         - L{gbp.git.GitVfs._File.read}
         - L{gbp.git.GitVfs._File.close}

    >>> import gbp.git.vfs
    >>> (repo, content) = setup_repo()
    >>> vfs = gbp.git.vfs.GitVfs(repo, 'HEAD')
    >>> gf = vfs.open('foo.txt')
    >>> gf.readline()
    'al pha\\n'
    >>> gf.readline()
    'a\\n'
    >>> gf.readlines()
    ['b\\n', 'c']
    >>> gf.readlines()
    []
    >>> gf.readline()
    ''
    >>> gf.readline()
    ''
    >>> gf.close()
    >>> gbp.git.vfs.GitVfs(repo, 'HEAD').open('foo.txt').read() == content
    True
    >>> gf = vfs.open('doesnotexist')
    Traceback (most recent call last):
    ...
    IOError: can't get HEAD:doesnotexist: fatal: Path 'doesnotexist' does not exist in 'HEAD'
    >>> context.teardown()
    """


def test_content_manager():
    """
    Create a repository

    Methods tested:
         - L{gbp.git.GitVfs.open}

    >>> import gbp.git.vfs
    >>> (repo, content) = setup_repo()
    >>> vfs = gbp.git.vfs.GitVfs(repo, 'HEAD')
    >>> with vfs.open('foo.txt') as gf:
    ...   data = gf.readlines()
    >>> data
    ['al pha\\n', 'a\\n', 'b\\n', 'c']
    """
