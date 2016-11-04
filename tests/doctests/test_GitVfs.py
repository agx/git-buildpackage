# vim: set fileencoding=utf-8 :

"""
Test L{gbp.git.GitVfs}
"""

import gbp.log

from .. import context  # noqa: F401

gbp.log.setup(color=False, verbose=True)


def test_read():
    """
    Create a repository

    Methods tested:
         - L{gbp.git.GitVfs.open}
         - L{gbp.git.GitVfs._File.readline}
         - L{gbp.git.GitVfs._File.readlines}
         - L{gbp.git.GitVfs._File.read}
         - L{gbp.git.GitVfs._File.close}

    >>> import os, gbp.git.vfs
    >>> repo_dir = context.new_tmpdir(__name__)
    >>> repo = gbp.git.GitRepository.create(str(repo_dir))
    >>> f = open(os.path.join(repo.path, 'foo.txt'), 'w')
    >>> content = 'al pha\\na\\nb\\nc'
    >>> ret = f.write('al pha\\na\\nb\\nc')
    >>> f.close()
    >>> repo.add_files(repo.path, force=True)
    >>> repo.commit_all(msg="foo")
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
