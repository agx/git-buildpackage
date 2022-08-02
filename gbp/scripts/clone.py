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
import yaml
from gbp.config import (GbpOptionParser, GbpOptionGroup)
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
    >>> repo_to_url("salsa:agx/git-buildpackage")
    'https://salsa.debian.org/agx/git-buildpackage.git'
    >>> repo_to_url("github:agx/git-buildpackage")
    'https://github.com/agx/git-buildpackage.git'
    """
    parts = repo.split(":", 1)
    if len(parts) != 2:
        return repo
    else:
        proto, path = parts

    if proto == 'salsa':
        return 'https://salsa.debian.org/%s.git' % path
    if proto == 'github':
        return 'https://github.com/%s.git' % path
    elif proto in ['vcsgit', 'vcs-git']:
        return vcs_git_url(path)
    else:
        return repo


def add_upstream_vcs(repo):
    upstream_info = os.path.join('debian', 'upstream', 'metadata')
    if not os.path.exists(upstream_info):
        gbp.log.warn("No upstream metadata, can't track upstream repo")
        return

    with open(upstream_info) as f:
        metadata = yaml.safe_load(f)
        url = metadata.get('Repository', None)

    if url is None:
        gbp.log.warn("No repository in metadata, can't track upstream repo")
        return

    gbp.log.info(f"Adding upstream vcs at {url} as additional remote")
    repo.add_remote_repo('upstreamvcs', url, fetch=True)


def build_parser(name):
    try:
        parser = GbpOptionParser(command=os.path.basename(name), prefix='',
                                 usage='%prog [options] repository - clone a remote repository')
    except GbpError as err:
        gbp.log.err(err)
        return None

    branch_group = GbpOptionGroup(parser, "branch options", "branch tracking and layout options")
    cmd_group = GbpOptionGroup(parser, "external command options", "how and when to invoke hooks")
    uvcs_group = GbpOptionGroup(parser, "upstream vcs options", "upstream vcs options")
    parser.add_option_group(branch_group)
    parser.add_option_group(cmd_group)
    parser.add_option_group(uvcs_group)

    branch_group.add_option("--all", action="store_true", dest="all", default=False,
                            help="track all branches, not only debian and upstream")
    branch_group.add_config_file_option(option_name="upstream-branch", dest="upstream_branch")
    branch_group.add_config_file_option(option_name="debian-branch", dest="debian_branch")
    branch_group.add_boolean_config_file_option(option_name="pristine-tar", dest="pristine_tar")
    branch_group.add_option("--depth", action="store", dest="depth", default=0,
                            help="git history depth (for creating shallow clones)")
    branch_group.add_option("--reference", action="store", dest="reference", default=None,
                            help="git reference repository (use local copies where possible)")
    cmd_group.add_config_file_option(option_name="postclone", dest="postclone",
                                     help="hook to run after cloning the source tree, "
                                     "default is '%(postclone)s'")
    cmd_group.add_boolean_config_file_option(option_name="hooks", dest="hooks")

    uvcs_group.add_boolean_config_file_option(option_name="add-upstream-vcs", dest='add_upstream_vcs')

    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    parser.add_config_file_option(option_name="repo-user", dest="repo_user",
                                  choices=['DEBIAN', 'GIT'])
    parser.add_config_file_option(option_name="repo-email", dest="repo_email",
                                  choices=['DEBIAN', 'GIT'])
    parser.add_config_file_option(option_name="defuse-gitattributes", dest="defuse_gitattributes",
                                  type="tristate", help="disable harmful Git attributes")
    parser.add_boolean_config_file_option(option_name="aliases", dest="aliases")
    return parser


def parse_args(argv):
    parser = build_parser(argv[0])
    if not parser:
        return None, None

    (options, args) = parser.parse_args(argv)
    gbp.log.setup(options.color, options.verbose, options.color_scheme)
    return (options, args)


def main(argv):
    retval = 0

    (options, args) = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    if len(args) < 2:
        gbp.log.err("Need a repository to clone.")
        return 1
    else:
        remote_repo = args[1]
        source = repo_to_url(remote_repo) if options.aliases else remote_repo
        if not source:
            return 1

    clone_to, auto_name = (os.path.curdir, True) if len(args) < 3 else (args[2], False)
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
        (options, args) = parse_args(argv)

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

        if repo.has_branch(options.debian_branch, remote=True):
            repo.set_branch(options.debian_branch)

        repo_setup.set_user_name_and_email(options.repo_user, options.repo_email, repo)
        if not options.defuse_gitattributes.is_off():
            if options.defuse_gitattributes.is_on() or not repo_setup.check_gitattributes(repo, 'HEAD'):
                repo_setup.setup_gitattributes(repo)

        if options.add_upstream_vcs:
            add_upstream_vcs(repo)

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
