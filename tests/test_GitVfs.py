# vim: set fileencoding=utf-8 :

"""
Test L{gbp.git.GitVfs}
"""

import os
import gbp.log

from . import context

gbp.log.setup(color=False, verbose=True)

def test_read():
    repo_dir = context.new_tmpdir(__name__)
    """
    Create a repository

    Methods tested:
         - L{gbp.git.GitVfs.open}
         - L{gbp.git._File.readline}
         - L{gbp.git._File.readlines}
         - L{gbp.git._File.read}
         - L{gbp.git._File.close}

    >>> import os, gbp.git.vfs
    >>> repo = gbp.git.GitRepository.create(str(repo_dir))
    >>> f = file(os.path.join(repo.path, 'foo.txt'), 'w')
    >>> content = 'al pha\\na\\nb\\nc'
    >>> f.write('al pha\\na\\nb\\nc')
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
    >>> gbp.git.vfs.GitVfs(repo, 'HEAD').open('foo.txt').read() == content
    True
    >>> gf = vfs.open('doesnotexist')
    Traceback (most recent call last):
    ...
    IOError: can't get HEAD:doesnotexist: fatal: Path 'doesnotexist' does not exist in 'HEAD'
    >>> context.teardown()
    """
