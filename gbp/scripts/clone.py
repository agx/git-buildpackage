# vim: set fileencoding=utf-8 :
#
# (C) 2009, 2010, 2015, 2017 Guido Günther <agx@sigxcpu.org>
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
# inspired by dom-git-checkout
#
"""Clone a Git repository and set it up for gbp"""

import re
import sys
import os
from gbp.config import GbpConfArgParser
from gbp.deb.git import DebianGitRepository
from gbp.git import (GitRepository, GitRepositoryError)
from gbp.errors import GbpError
from gbp.scripts.common import ExitCodes
from gbp.scripts.common import repo_setup
from gbp.scripts.common.hook import Hook
from gbp.command_wrappers import Command, CommandExecFailed
from gbp.deb import DpkgCompareVersions
import gbp.log

from functools import cmp_to_key


def apt_showsrc(pkg):
    try:
        aptsrc = Command("apt-cache", ["showsrc", pkg], capture_stdout=True)
        aptsrc(quiet=True)
        return aptsrc.stdout
    except CommandExecFailed:
        return ''


def vcs_git_url(pkg):
    repos = {}

    out = apt_showsrc(pkg)
    vcs_re = re.compile(r'(x-)?vcs-git:\s*(?P<repo>[^ ]+)$', re.I)
    version_re = re.compile(r'Version:\s*(?P<version>.*)$', re.I)
    end_re = re.compile(r'\s*$')

    version = repo = None
    for line in out.split('\n'):
        m = vcs_re.match(line)
        if m:
            repo = m.group('repo')
            continue
        m = version_re.match(line)
        if m:
            version = m.group('version')
            continue
        m = end_re.match(line)
        if m:
            if version and repo:
                repos[version] = repo
            version = repo = None

    if not repos:
        gbp.log.err("Can't find any vcs-git URL for '%s'" % pkg)
        return None

    s = sorted(repos, key=cmp_to_key(DpkgCompareVersions()))
    return repos[s[-1]]


def repo_to_url(repo):
    """
    >>> repo_to_url("https://foo.example.com")
    'https://foo.example.com'
    >>> repo_to_url("github:agx/git-buildpackage")
    'https://github.com/agx/git-buildpackage.git'
    """
    parts = repo.split(":", 1)
    if len(parts) != 2:
        return repo
    else:
        proto, path = parts

    if proto == 'github':
        return 'https://github.com/%s.git' % path
    elif proto in ['vcsgit', 'vcs-git']:
        return vcs_git_url(path)
    else:
        return repo


def build_parser(name):
    try:
        parser = GbpConfArgParser.create_parser(prog=name,
                                                description='clone a remote repository')
    except GbpError as err:
        gbp.log.err(err)
        return None

    branch_group = parser.add_argument_group("branch options", "branch tracking and layout options")
    cmd_group = parser.add_argument_group("external command options", "how and when to invoke hooks")

    branch_group.add_arg("--all", action="store_true", dest="all",
                         help="track all branches, not only debian and upstream")
    branch_group.add_conf_file_arg("--upstream-branch", dest="upstream_branch")
    branch_group.add_conf_file_arg("--debian-branch", dest="debian_branch")
    branch_group.add_bool_conf_file_arg("--pristine-tar", dest="pristine_tar")
    branch_group.add_arg("--depth", action="store", dest="depth", default=0,
                         help="git history depth (for creating shallow clones)")
    branch_group.add_arg("--reference", action="store", dest="reference", default=None,
                         help="git reference repository (use local copies where possible)")
    cmd_group.add_conf_file_arg("--postclone", dest="postclone",
                                help="hook to run after cloning the source tree")
    cmd_group.add_bool_conf_file_arg("--hooks", dest="hooks")

    parser.add_arg("-v", "--verbose", action="store_true", dest="verbose",
                   help="verbose command execution")
    parser.add_conf_file_arg("--color", dest="color", type='tristate')
    parser.add_conf_file_arg("--color-scheme", dest="color_scheme")
    parser.add_conf_file_arg("--repo-user", dest="repo_user",
                             choices=['DEBIAN', 'GIT'])
    parser.add_conf_file_arg("--repo-email", dest="repo_email",
                             choices=['DEBIAN', 'GIT'])
    parser.add_argument("repository", metavar="REPOSITORY",
                        help="repository to clone")
    parser.add_argument("directory", metavar="DIRECTORY", nargs="?",
                        help="local directory to clone into")
    return parser


def parse_args(argv):
    parser = build_parser(argv[0])
    if not parser:
        return None

    options = parser.parse_args(argv[1:])
    gbp.log.setup(options.color, options.verbose, options.color_scheme)
    return options


def main(argv):
    retval = 0

    options = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    source = repo_to_url(options.repository)
    if not source:
        return 1

    clone_to, auto_name = (os.path.curdir, True) if not options.directory \
        else (options.directory, False)
    try:
        GitRepository(clone_to)
        gbp.log.err("Can't run inside a git repository.")
        return 1
    except GitRepositoryError:
        pass

    try:
        gbp.log.info("Cloning from '%s'%s" % (source, " into '%s'" % clone_to if not auto_name else ''))
        repo = DebianGitRepository.clone(clone_to, source, options.depth,
                                         auto_name=auto_name, reference=options.reference)
        os.chdir(repo.path)

        # Reparse the config files of the cloned repository so we pick up the
        # branch information from there but don't overwrite hooks:
        postclone = options.postclone
        options = parse_args(argv)

        # Track all branches:
        if options.all:
            remotes = repo.get_remote_branches()
            for remote in remotes:
                local = remote.replace("origin/", "", 1)
                if (not repo.has_branch(local) and
                        local != "HEAD"):
                    repo.create_branch(local, remote)
        else:  # only track gbp's default branches
            branches = [options.debian_branch, options.upstream_branch]
            if options.pristine_tar:
                branches += [repo.pristine_tar_branch]
            gbp.log.debug('Will track branches: %s' % branches)
            for branch in branches:
                remote = 'origin/%s' % branch
                if (repo.has_branch(remote, remote=True) and
                        not repo.has_branch(branch)):
                    repo.create_branch(branch, remote)

        repo.set_branch(options.debian_branch)

        repo_setup.set_user_name_and_email(options.repo_user, options.repo_email, repo)

        if postclone:
            Hook('Postclone', options.postclone,
                 extra_env={'GBP_GIT_DIR': repo.git_dir},
                 )()

    except KeyboardInterrupt:
        retval = 1
        gbp.log.err("Interrupted. Aborting.")
    except GitRepositoryError as err:
        gbp.log.err("Git command failed: %s" % err)
        retval = 1
    except GbpError as err:
        if str(err):
            gbp.log.err(err)
        retval = 1

    return retval


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
