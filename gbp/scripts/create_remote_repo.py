# vim: set fileencoding=utf-8 :
#
# (C) 2010,2012 Guido Günther <agx@sigxcpu.org>
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Based on the aa-create-git-repo and dom-new-git-repo shell scripts
"""Create a remote repo based on the current one"""

import sys
import os, os.path
import urlparse
import subprocess
import tty, termios
import re
from gbp.deb.changelog import ChangeLog, NoChangeLogError
from gbp.command_wrappers import (CommandExecFailed, GitCommand)
from gbp.config import (GbpOptionParserDebian, GbpOptionGroup)
from gbp.errors import GbpError
from gbp.git import GitRepositoryError
from gbp.deb.git import DebianGitRepository
import gbp.log

def print_config(remote, branches):
    """
    Print out the git config to push to the newly created repo.

    >>> print_config({'name': 'name', 'url': 'url'}, ['foo', 'bar'])
    [remote "name"]
            url = url
            fetch = +refs/heads/*:refs/remotes/name/*
            push = foo
            push = bar
    [branch "foo"]
            remote = name
            merge = refs/heads/foo
    [branch "bar"]
            remote = name
            merge = refs/heads/bar
    """

    print """[remote "%(name)s"]
        url = %(url)s
        fetch = +refs/heads/*:refs/remotes/%(name)s/*""" % remote

    for branch in branches:
        print "        push = %s" % branch

    for branch in branches:
        print """[branch "%s"]
        remote = %s
        merge = refs/heads/%s""" % (branch, remote['name'], branch)

def sort_dict(d):
    """Return a sorted list of (key, value) tuples"""
    s = []
    for key in sorted(d.iterkeys()):
        s.append((key, d[key]))
    return s

def parse_url(remote_url, name, pkg, template_dir=None):
    """
    Sanity check our remote URL

    >>> sort_dict(parse_url("ssh://host/path/%(pkg)s", "origin", "package"))
    [('base', ''), ('dir', '/path/package'), ('host', 'host'), ('name', 'origin'), ('pkg', 'package'), ('port', None), ('scheme', 'ssh'), ('template-dir', None), ('url', 'ssh://host/path/package')]

    >>> sort_dict(parse_url("ssh://host:22/path/repo.git", "origin", "package"))
    [('base', ''), ('dir', '/path/repo.git'), ('host', 'host'), ('name', 'origin'), ('pkg', 'package'), ('port', '22'), ('scheme', 'ssh'), ('template-dir', None), ('url', 'ssh://host:22/path/repo.git')]

    >>> sort_dict(parse_url("ssh://host:22/~/path/%(pkg)s.git", "origin", "package"))
    [('base', '~/'), ('dir', 'path/package.git'), ('host', 'host'), ('name', 'origin'), ('pkg', 'package'), ('port', '22'), ('scheme', 'ssh'), ('template-dir', None), ('url', 'ssh://host:22/~/path/package.git')]

    >>> sort_dict(parse_url("ssh://host:22/~user/path/%(pkg)s.git", "origin", "package", "/doesnot/exist"))
    [('base', '~user/'), ('dir', 'path/package.git'), ('host', 'host'), ('name', 'origin'), ('pkg', 'package'), ('port', '22'), ('scheme', 'ssh'), ('template-dir', '/doesnot/exist'), ('url', 'ssh://host:22/~user/path/package.git')]

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
    frags = urlparse.urlparse(remote_url)
    if frags.scheme in ['ssh', 'git+ssh', '']:
        scheme = frags.scheme
    else:
        raise GbpError("URL must use ssh protocol.")

    if not '%(pkg)s' in remote_url and not remote_url.endswith(".git"):
        raise GbpError("URL needs to contain either a repository name or '%(pkg)s'")

    if ":" in frags.netloc:
        (host, port) = frags.netloc.split(":", 1)
        if not re.match(r"^[0-9]+$", port):
            raise GbpError("URL contains invalid port.")
    else:
        host = frags.netloc
        port = None

    if frags.path.startswith("/~"):
        m = re.match(r"/(~[a-zA-Z0-9_-]*/)(.*)", frags.path)
        if not m:
            raise GbpError("URL contains invalid ~username expansion.")
        base = m.group(1)
        path = m.group(2)
    else:
        base = ""
        path = frags.path

    remote = { 'pkg' : pkg,
               'url' : remote_url % { 'pkg': pkg },
               'dir' : path % { 'pkg': pkg },
               'base': base,
               'host': host,
               'port': port,
               'name': name,
               'scheme': scheme,
               'template-dir': template_dir}
    return remote


def build_remote_script(remote):
    """
    Create the script that will be run on the remote side
    >>> build_remote_script({'base': 'base', 'dir': 'dir', 'pkg': 'pkg', 'template-dir': None})
    '\\nset -e\\numask 002\\nif [ -d base"dir" ]; then\\n  echo "Repository at "basedir" already exists - giving up."\\n  exit 1\\nfi\\nmkdir -p base"dir"\\ncd base"dir"\\ngit init --bare --shared\\necho "pkg packaging" > description\\n'
    >>> build_remote_script({'base': 'base', 'dir': 'dir', 'pkg': 'pkg', 'template-dir': '/doesnot/exist'})
    '\\nset -e\\numask 002\\nif [ -d base"dir" ]; then\\n  echo "Repository at "basedir" already exists - giving up."\\n  exit 1\\nfi\\nmkdir -p base"dir"\\ncd base"dir"\\ngit init --bare --shared --template=/doesnot/exist\\necho "pkg packaging" > description\\n'

    """
    remote = remote
    remote['git-init-args'] = '--bare --shared'
    if remote['template-dir']:
        remote['git-init-args'] += (' --template=%s'
                                    % remote['template-dir'])
    remote_script_pattern = ['',
      'set -e',
      'umask 002',
      'if [ -d %(base)s"%(dir)s" ]; then',
      '  echo "Repository at \"%(base)s%(dir)s\" already exists - giving up."',
      '  exit 1',
      'fi',
      'mkdir -p %(base)s"%(dir)s"',
      'cd %(base)s"%(dir)s"',
      'git init %(git-init-args)s',
      'echo "%(pkg)s packaging" > description',
      '' ]
    remote_script = '\n'.join(remote_script_pattern) % remote
    return remote_script


def build_cmd(remote):
    """
    Build the command we pass the script to

    >>> build_cmd({'scheme': ''})
    ['sh']
    >>> build_cmd({'scheme': 'ssh', 'host': 'host', 'port': 80})
    ['ssh', '-p', 80, 'host', 'sh']
    """
    cmd = []
    if remote["scheme"]:
        cmd.append('ssh')
        if remote["port"]:
            cmd.extend(['-p', remote['port']])
        cmd.append(remote["host"])
    cmd.append('sh')
    return cmd


def read_yn():
    fd = sys.stdin.fileno()
    try:
        old_settings = termios.tcgetattr(fd)
    except termios.error:
        old_settings = None

    try:
        if old_settings:
            tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        if old_settings:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    if ch in ( 'y', 'Y' ):
        return True
    else:
        return False


def setup_branch_tracking(repo, remote, branches):
    repo.add_remote_repo(name=remote['name'], url=remote['url'], fetch=True)
    gitTrackRemote = GitCommand('branch', ['--set-upstream'])
    for branch in branches:
        gitTrackRemote(['%s' % branch, '%s/%s' % (remote['name'], branch)])


def push_branches(remote, branches):
    gitPush = GitCommand('push')
    gitPush([remote['url']] + branches)
    gitPush([remote['url'], '--tags'])


def parse_args(argv, sections=[]):
    """
    Parse the command line arguments and config files.

    @param argv: the command line arguments
    @type argv: C{list} of C{str}
    @param sections: additional sections to add to the config file parser
        besides the command name
    @type sections: C{list} of C{str}
    """

    # We simpley handle the template section as an additional config file
    # section to parse, this makes e.g. --help work as expected:
    for arg in argv:
        if arg.startswith('--remote-config='):
            sections = ['remote-config %s' % arg.split('=',1)[1]]
            break
    else:
        sections = []

    parser = GbpOptionParserDebian(command=os.path.basename(argv[0]), prefix='',
                                   usage='%prog [options] - '
                                   'create a remote repository',
                                   sections=sections)
    branch_group = GbpOptionGroup(parser,
                                  "branch options",
                                  "branch layout and tracking options")
    branch_group.add_config_file_option(option_name="remote-url-pattern",
                                        dest="remote_url")
    parser.add_option_group(branch_group)
    branch_group.add_config_file_option(option_name="upstream-branch",
                                        dest="upstream_branch")
    branch_group.add_config_file_option(option_name="debian-branch",
                                        dest="debian_branch")
    branch_group.add_boolean_config_file_option(option_name="pristine-tar",
                                                dest="pristine_tar")
    branch_group.add_boolean_config_file_option(option_name="track",
                                                dest='track')
    parser.add_option("-v", "--verbose",
                      action="store_true",
                      dest="verbose",
                      default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color",
                                  dest="color",
                                  type='tristate')
    parser.add_option("--remote-name",
                      dest="name",
                      default="origin",
                      help="The name of the remote, default is 'origin'")
    parser.add_config_file_option(option_name="template-dir",
                                  dest="template_dir")
    parser.add_config_file_option(option_name="remote-config",
                                  dest="remote_config")

    (options, args) = parser.parse_args(argv)

    return options, args


def main(argv):
    retval = 0
    changelog = 'debian/changelog'
    cmd = []

    try:
        options, args = parse_args(argv)
    except Exception as e:
        print >>sys.stderr, "%s" % e
        return 1

    gbp.log.setup(options.color, options.verbose)
    try:
        repo = DebianGitRepository(os.path.curdir)
    except GitRepositoryError:
        gbp.log.err("%s is not a git repository" % (os.path.abspath('.')))
        return 1

    try:
        branches = []

        for branch in [ options.debian_branch, options.upstream_branch ]:
            if repo.has_branch(branch):
                branches += [ branch ]

        if repo.has_pristine_tar_branch() and options.pristine_tar:
            branches += [ repo.pristine_tar_branch ]

        try:
            cp = ChangeLog(filename=changelog)
            pkg = cp['Source']
        except NoChangeLogError:
            pkg = None

        if not pkg:
            gbp.log.warn("Couldn't parse changelog, will use directory name.")
            pkg = os.path.basename(os.path.abspath(os.path.curdir))
            pkg = os.path.splitext(pkg)[0]

        remote = parse_url(options.remote_url,
                           options.name,
                           pkg,
                           options.template_dir)
        if repo.has_remote_repo(options.name):
            raise GbpError("You already have a remote name '%s' defined for this repository." % options.name)

        gbp.log.info("Shall I create a repository for '%(pkg)s' at '%(url)s' now? (y/n)?" % remote)
        if not read_yn():
            raise GbpError("Aborted.")

        remote_script = build_remote_script(remote)
        if options.verbose:
            print remote_script

        cmd = build_cmd(remote)
        if options.verbose:
            print cmd

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        proc.communicate(remote_script)
        if proc.returncode:
            raise GbpError("Error creating remote repository")

        push_branches(remote, branches)
        if options.track:
            setup_branch_tracking(repo, remote, branches)
        else:
            gbp.log.info("You can now add:")
            print_config(remote, branches)
            gbp.log.info("to your .git/config to 'gbp-pull' and 'git push' in the future.")

    except CommandExecFailed:
        retval = 1
    except (GbpError, GitRepositoryError) as err:
        if len(err.__str__()):
            gbp.log.err(err)
        retval = 1

    return retval

if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
