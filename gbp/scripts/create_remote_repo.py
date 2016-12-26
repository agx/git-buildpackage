# vim: set fileencoding=utf-8 :
#
# (C) 2010,2012,2015,2016 Guido Günther <agx@sigxcpu.org>
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
#    along with this program; if not, please see
#    <http://www.gnu.org/licenses/>
#
# Based on the aa-create-git-repo and dom-new-git-repo shell scripts
"""Create a remote Git repository based on the current one"""

from __future__ import print_function

import sys
import os
from six.moves import urllib
import subprocess
import tty
import termios
import re
from six.moves import configparser

from gbp.deb.changelog import ChangeLog, NoChangeLogError
from gbp.command_wrappers import (CommandExecFailed, GitCommand)
from gbp.config import (GbpOptionParserDebian, GbpOptionGroup)
from gbp.errors import GbpError
from gbp.git import GitRepositoryError
from gbp.deb.git import DebianGitRepository
from gbp.scripts.common import ExitCodes

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

    print("""[remote "%(name)s"]
        url = %(url)s
        fetch = +refs/heads/*:refs/remotes/%(name)s/*""" % remote)

    for branch in branches:
        print("        push = %s" % branch)

    for branch in branches:
        print("""[branch "%s"]
        remote = %s
        merge = refs/heads/%s""" % (branch, remote['name'], branch))


def parse_url(remote_url, name, pkg, template_dir=None, bare=True):
    """
    Sanity check our remote URL

    """
    frags = urllib.parse.urlparse(remote_url)
    if frags.scheme in ['ssh', 'git+ssh', '']:
        scheme = frags.scheme
    else:
        raise GbpError("URL must use ssh protocol.")

    if '%(pkg)s' not in remote_url and not remote_url.endswith(".git"):
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

    remote = {'pkg': pkg,
              'url': remote_url % {'pkg': pkg},
              'dir': path % {'pkg': pkg},
              'base': base,
              'host': host,
              'port': port,
              'name': name,
              'scheme': scheme,
              'template-dir': template_dir,
              'bare': bare}
    return remote


def build_remote_script(remote, branch):
    """
    Create the script that will be run on the remote side
    """
    args = remote
    args['branch'] = branch
    args['git-init-args'] = '--shared'
    if args['bare']:
        args['git-init-args'] += ' --bare'
        args['checkout_cmd'] = ''
        args['git_dir'] = '.'
    else:
        args['checkout_cmd'] = 'git checkout -f'
        args['git_dir'] = '.git'
    if args['template-dir']:
        args['git-init-args'] += (' --template=%s'
                                  % args['template-dir'])
    remote_script_pattern = \
        ['',
         'set -e',
         'umask 002',
         'if [ -d %(base)s"%(dir)s" ]; then',
         '  echo "Repository at \"%(base)s%(dir)s\" already exists - giving up."',
         '  exit 1',
         'fi',
         'mkdir -p %(base)s"%(dir)s"',
         'cd %(base)s"%(dir)s"',
         'git init %(git-init-args)s',
         'echo "%(pkg)s packaging" > %(git_dir)s/description',
         'echo "ref: refs/heads/%(branch)s" > %(git_dir)s/HEAD',
         '']
    remote_script = '\n'.join(remote_script_pattern) % args
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

    if ch in ('y', 'Y'):
        return True
    else:
        return False


def setup_branch_tracking(repo, remote, branches):
    repo.add_remote_repo(name=remote['name'], url=remote['url'], fetch=True)
    gitTrackRemote = GitCommand('branch', ['--set-upstream-to'])
    for branch in branches:
        gitTrackRemote(['%s/%s' % (remote['name'], branch), branch])


def push_branches(remote, branches):
    gitPush = GitCommand('push')
    gitPush([remote['url']] + branches)
    gitPush([remote['url'], '--tags'])


def usage_msg():
    return """%prog [options] - create a remote git repository
Actions:
  create         create the repository. This is the default when no action is
                 given.
  list           list available configuration templates for remote repositories"""


def build_parser(name, sections=[]):
    try:
        parser = GbpOptionParserDebian(command=os.path.basename(name), prefix='',
                                       usage=usage_msg(),
                                       sections=sections)
    except (GbpError, configparser.NoSectionError) as err:
        gbp.log.err(err)
        return None

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
    branch_group.add_boolean_config_file_option(option_name="bare",
                                                dest='bare')
    parser.add_option("-v", "--verbose",
                      action="store_true",
                      dest="verbose",
                      default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color",
                                  dest="color",
                                  type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    parser.add_option("--remote-name",
                      dest="name",
                      default="origin",
                      help="The name of the remote, default is 'origin'")
    parser.add_config_file_option(option_name="template-dir",
                                  dest="template_dir")
    parser.add_config_file_option(option_name="remote-config",
                                  dest="remote_config")
    return parser


def parse_args(argv):
    """
    Parse the command line arguments and config files.

    @param argv: the command line arguments
    @type argv: C{list} of C{str}
    """
    sections = []
    # We handle the template section as an additional config file
    # section to parse, this makes e.g. --help work as expected:
    for arg in argv:
        if arg.startswith('--remote-config='):
            sections = ['remote-config %s' % arg.split('=', 1)[1]]
            break

    parser = build_parser(argv[0], sections)
    if not parser:
        return None, None, None

    return list(parser.parse_args(argv)) + [parser.config_file_sections]


def do_create(options):
    retval = 0
    changelog = 'debian/changelog'
    cmd = []

    try:
        repo = DebianGitRepository(os.path.curdir)
    except GitRepositoryError:
        gbp.log.err("%s is not a git repository" % (os.path.abspath('.')))
        return 1

    try:
        branches = []

        for branch in [options.debian_branch, options.upstream_branch]:
            if repo.has_branch(branch):
                branches += [branch]

        if repo.has_pristine_tar_branch() and options.pristine_tar:
            branches += [repo.pristine_tar_branch]

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
                           options.template_dir,
                           options.bare)
        if repo.has_remote_repo(options.name):
            raise GbpError("You already have a remote name '%s' defined for this repository." % options.name)

        gbp.log.info("Shall I create a repository for '%(pkg)s' at '%(url)s' now? (y/n)?" % remote)
        if not read_yn():
            raise GbpError("Aborted.")

        remote_default = branches[0] if branches else options.debian_branch
        remote_script = build_remote_script(remote, remote_default)
        if options.verbose:
            print(remote_script)

        cmd = build_cmd(remote)
        if options.verbose:
            print(cmd)

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        proc.communicate(remote_script)
        if proc.returncode:
            raise GbpError("Error creating remote repository")

        if branches:
            push_branches(remote, branches)
        if options.track:
            setup_branch_tracking(repo, remote, branches)
        else:
            gbp.log.info("You can now add:")
            print_config(remote, branches)
            gbp.log.info("to your .git/config to 'gbp pull' and 'git push' in the future.")
    except KeyboardInterrupt:
        retval = 1
        gbp.log.err("Interrupted. Aborting.")
    except CommandExecFailed:
        retval = 1
    except (GbpError, GitRepositoryError) as err:
        if str(err):
            gbp.log.err(err)
        retval = 1
    return retval


def get_config_names(sections):
    config_names = []
    for section in sections:
        if section.startswith("remote-config "):
            config_names.append(section.split(' ', 1)[1])
    return config_names


def do_list(sections):
    names = get_config_names(sections)
    if names:
        gbp.log.info("Available remote config templates:")
        for n in names:
            print("    %s" % n)
    else:
        gbp.log.info("No remot config templates found.")
    return 0


def main(argv):
    retval = 1

    options, args, sections = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    if len(args) == 1:
        args.append('create')  # the default
    elif len(args) > 2:
        gbp.log.err("Only one action allowed")
        return 1

    action = args[1]
    if action == 'create':
        retval = do_create(options)
    elif action == 'list':
        retval = do_list(sections)
    else:
        gbp.log.err("Unknown action '%s'" % action)
    return retval


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
