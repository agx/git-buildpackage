# vim: set fileencoding=utf-8 :

from gbp.scripts.create_remote_repo import (build_remote_script,  # noqa: F401
                                            parse_url)            # noqa: F401


def test_template_dir():
    """
    >>> build_remote_script({'base': 'base', 'dir': 'dir', 'pkg': 'pkg', 'template-dir': None}, 'branch')
    '\\nset -e\\numask 002\\nif [ -d base"dir" ]; then\\n  echo "Repository at "basedir" already exists - giving up."\\n  exit 1\\nfi\\nmkdir -p base"dir"\\ncd base"dir"\\ngit init --bare --shared\\necho "pkg packaging" > description\\necho "ref: refs/heads/branch" > HEAD\\n'
    >>> build_remote_script({'base': 'base', 'dir': 'dir', 'pkg': 'pkg', 'template-dir': '/doesnot/exist'}, 'branch')
    '\\nset -e\\numask 002\\nif [ -d base"dir" ]; then\\n  echo "Repository at "basedir" already exists - giving up."\\n  exit 1\\nfi\\nmkdir -p base"dir"\\ncd base"dir"\\ngit init --bare --shared --template=/doesnot/exist\\necho "pkg packaging" > description\\necho "ref: refs/heads/branch" > HEAD\\n'
    """


def test_parse_url():
    """
    >>> url = parse_url("ssh://host/path/%(pkg)s", "origin", "package")
    >>> url['base']
    ''
    >>> url['dir']
    '/path/package'
    >>> url['host']
    'host'
    >>> url['name']
    'origin'
    >>> url['pkg']
    'package'
    >>> url['port']
    >>> url['scheme']
    'ssh'
    >>> url['template-dir']
    >>> url['url']
    'ssh://host/path/package'

    >>> url = parse_url("ssh://host:22/path/to/repo.git", "origin", "package")
    >>> url['base']
    ''
    >>> url['dir']
    '/path/to/repo.git'
    >>> url['host']
    'host'
    >>> url['name']
    'origin'
    >>> url['pkg']
    'package'
    >>> url['port']
    '22'
    >>> url['scheme']
    'ssh'
    >>> url['template-dir']
    >>> url['url']
    'ssh://host:22/path/to/repo.git'

    >>> url = parse_url("ssh://host:22/~/path/%(pkg)s.git", "origin", "package")
    >>> url['dir']
    'path/package.git'
    >>> url['host']
    'host'
    >>> url['name']
    'origin'
    >>> url['pkg']
    'package'
    >>> url['port']
    '22'
    >>> url['scheme']
    'ssh'
    >>> url['template-dir']
    >>> url['url']
    'ssh://host:22/~/path/package.git'

    >>> url = parse_url("ssh://host:22/~user/path/%(pkg)s.git", "origin", "package", "/doesnot/exist")
    >>> url['dir']
    'path/package.git'
    >>> url['host']
    'host'
    >>> url['name']
    'origin'
    >>> url['pkg']
    'package'
    >>> url['port']
    '22'
    >>> url['scheme']
    'ssh'
    >>> url['template-dir']
    '/doesnot/exist'
    >>> url['url']
    'ssh://host:22/~user/path/package.git'

    >>> parse_url("git://host/repo.git", "origin", "package")
    Traceback (most recent call last):
        ...
    GbpError: URL must use ssh protocol.
    >>> parse_url("ssh://host/path/repo", "origin", "package")
    Traceback (most recent call last):
        ...
    GbpError: URL needs to contain either a repository name or '%(pkg)s'
    >>> parse_url("ssh://host:asdf/path/%(pkg)s.git", "origin", "package")
    Traceback (most recent call last):
        ...
    GbpError: URL contains invalid port.
    >>> parse_url("ssh://host/~us er/path/%(pkg)s.git", "origin", "package")
    Traceback (most recent call last):
        ...
    GbpError: URL contains invalid ~username expansion.
    """
