# vim: set fileencoding=utf-8 :
#
# (C) 2010 Guido Guenther <agx@sigxcpu.org>
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
# TODO: allow to add hooks by default

import sys
import os, os.path
import urlparse
import subprocess
import tty, termios
import re
from gbp.deb.changelog import ChangeLog, NoChangeLogError
from gbp.command_wrappers import (CommandExecFailed, PristineTar, GitCommand)
from gbp.config import (GbpOptionParser, GbpOptionGroup)
from gbp.errors import GbpError
from gbp.git import (GitRepositoryError, GitRepository)
import gbp.log

def print_config(remote, branches):
    print """[remote "%(name)s"]
        url = %(url)s
        fetch = +refs/heads/*:refs/remotes/%(name)s/*""" % remote

    for branch in branches:
        print "        push = %s" % branch

    for branch in branches:
        print """[branch "%s"]
        remote = %s
        merge = refs/heads/%s""" % (branch, remote['name'], branch)


def parse_remote(remote_url, name, pkg):
    """
    Sanity check our remote URL

    >>> parse_remote("ssh://host/path/%(pkg)s", "origin", "package")
    {'name': 'origin', 'url': 'ssh://host/path/package', 'host': 'host', 'base': '', 'pkg': 'package', 'port': None, 'dir': '/path/package'}

    >>> parse_remote("ssh://host:22/path/repo.git", "origin", "package")
    {'name': 'origin', 'url': 'ssh://host:22/path/repo.git', 'host': 'host', 'base': '', 'pkg': 'package', 'port': '22', 'dir': '/path/repo.git'}

    >>> parse_remote("ssh://host:22/~/path/%(pkg)s.git", "origin", "package")
    {'name': 'origin', 'url': 'ssh://host:22/~/path/package.git', 'host': 'host', 'base': '~/', 'pkg': 'package', 'port': '22', 'dir': 'path/package.git'}

    >>> parse_remote("ssh://host:22/~user/path/%(pkg)s.git", "origin", "package")
    {'name': 'origin', 'url': 'ssh://host:22/~user/path/package.git', 'host': 'host', 'base': '~user/', 'pkg': 'package', 'port': '22', 'dir': 'path/package.git'}

    >>> parse_remote("git://host/repo.git", "origin", "package")
    Traceback (most recent call last):
        ...
    GbpError: Remote URL must use ssh protocol.
    >>> parse_remote("ssh://host/path/repo", "origin", "package")
    Traceback (most recent call last):
        ...
    GbpError: Remote URL needs to contain either a repository name or '%(pkg)s'
    >>> parse_remote("ssh://host:asdf/path/%(pkg)s.git", "origin", "package")
    Traceback (most recent call last):
        ...
    GbpError: Remote URL contains invalid port.
    >>> parse_remote("ssh://host/~us er/path/%(pkg)s.git", "origin", "package")
    Traceback (most recent call last):
        ...
    GbpError: Remote URL contains invalid ~username expansion.
    """
    frags = urlparse.urlparse(remote_url)
    if frags.scheme not in ['ssh', 'git+ssh']:
        raise GbpError, "Remote URL must use ssh protocol."
    if not '%(pkg)s' in remote_url and not remote_url.endswith(".git"):
        raise GbpError, "Remote URL needs to contain either a repository name or '%(pkg)s'"

    if ":" in frags.netloc:
        (host, port) = frags.netloc.split(":", 1)
        if not re.match(r"^[0-9]+$", port):
            raise GbpError, "Remote URL contains invalid port."
    else:
        host = frags.netloc
        port = None

    if frags.path.startswith("/~"):
        m = re.match(r"/(~[a-zA-Z0-9_-]*/)(.*)", frags.path)
        if not m:
            raise GbpError, "Remote URL contains invalid ~username expansion."
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
               'name': name}
    return remote


def read_yn():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
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


def main(argv):
    retval = 0
    changelog = 'debian/changelog'

    parser = GbpOptionParser(command=os.path.basename(argv[0]), prefix='',
                             usage='%prog [options] - create a remote repository')
    branch_group = GbpOptionGroup(parser, "branch options", "branch layout and tracking options")
    branch_group.add_config_file_option(option_name="remote-url-pattern", dest="remote_url")
    parser.add_option_group(branch_group)
    branch_group.add_config_file_option(option_name="upstream-branch", dest="upstream_branch")
    branch_group.add_config_file_option(option_name="debian-branch", dest="debian_branch")
    branch_group.add_boolean_config_file_option(option_name="pristine-tar", dest="pristine_tar")
    branch_group.add_boolean_config_file_option(option_name="track", dest='track')
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_option("--remote-name", dest="name", default="origin",
                      help="The name of the remote, default is 'origin'")

    (options, args) = parser.parse_args(argv)
    gbp.log.setup(options.color, options.verbose)

    try:
        repo = GitRepository(os.path.curdir)
    except GitRepositoryError:
        gbp.log.err("%s is not a git repository" % (os.path.abspath('.')))
        return 1

    try:
        branches = []

        for branch in [ options.debian_branch, options.upstream_branch ]:
            if repo.has_branch(branch):
                branches += [ branch ]

        if repo.has_branch(PristineTar.branch) and options.pristine_tar:
            branches += [ PristineTar.branch ]

        try:
            cp = ChangeLog(filename=changelog)
            pkg = cp['Source']
        except NoChangeLogError:
            pkg = None

        if not pkg:
            gbp.log.warn("Couldn't parse changelog, will use directory name.")
            pkg = os.path.basename(os.path.abspath(os.path.curdir))
            pkg = os.path.splitext(pkg)[0]

        remote = parse_remote(options.remote_url, options.name, pkg)
        if repo.has_remote_repo(options.name):
            raise GbpError, "You already have a remote name '%s' defined for this repository." % options.name
        gbp.log.info("Shall I create a repository for '%(pkg)s' at '%(url)s' now? (y/n)?" % remote)
        if not read_yn():
            raise GbpError, "Aborted."

        # Create and run the remote script
        remote_script =  """
set -e
umask 002
if [ -d %(base)s"%(dir)s" ]; then
    echo "Repository at \"%(base)s%(dir)s\" already exists - giving up."
    exit 1
fi
mkdir -p %(base)s"%(dir)s"
cd %(base)s"%(dir)s"
git init --bare --shared
echo "%(pkg)s packaging" > description
""" % remote

        if options.verbose:
            print remote_script

        ssh = ["ssh"]
        if remote["port"]:
            ssh.extend(["-p", remote["port"]])
        ssh.extend([remote["host"], "sh"])

        proc = subprocess.Popen(ssh, stdin=subprocess.PIPE)
        proc.communicate(remote_script)
        if proc.returncode:
            raise GbpError, "Error creating remote repository"

        push_branches(remote, branches)
        if options.track:
            setup_branch_tracking(repo, remote, branches)
        else:
            gbp.log.info("You can now add:")
            print_config(remote, branches)
            gbp.log.info("to your .git/config to 'gbp-pull' and 'git push' in the future.")

    except CommandExecFailed:
        retval = 1
    except GbpError, err:
        if len(err.__str__()):
            gbp.log.err(err)
        retval = 1

    return retval

if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
