# vim: set fileencoding=utf-8 :
#
# (C) 2009,2013,2017,2018 Guido Günther <agx@sigxcpu.org>
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
# heavily inspired by dom-safe-pull which is © 2009 Stéphane Glondu <steph@glondu.net>
#
"""Pull remote changes and fast forward debian, upstream and pristine-tar branch"""

import sys
import os
import os.path
from gbp.command_wrappers import (Command, CommandExecFailed)
from gbp.config import GbpConfArgParserDebian
from gbp.errors import GbpError
from gbp.git import GitRepositoryError
from gbp.deb.git import DebianGitRepository
from gbp.scripts.common import ExitCodes
import gbp.log


def fast_forward_branch(rem_repo, branch, repo, options):
    """
    update branch to its remote branch, fail on non fast forward updates
    unless --force is given
    @return: branch updated or already up to date
    @rtype: boolean
    """
    update = False

    if rem_repo:
        remote = 'refs/remotes/%s/%s' % (rem_repo, branch)
    else:
        remote = repo.get_merge_branch(branch)

    if not remote:
        gbp.log.warn("No branch tracking '%s' found - skipping." % branch)
        return False

    can_fast_forward, up_to_date = repo.is_fast_forward(branch, remote)

    if up_to_date:  # Great, we're done
        gbp.log.info("Branch '%s' is already up to date." % branch)
        return True

    if can_fast_forward:
        update = True
    else:
        if options.force:
            gbp.log.info("Non-fast forwarding '%s' due to --force" % branch)
            update = True
        else:
            gbp.log.warn("Skipping non-fast forward of '%s' - use --force or "
                         "update manually" % branch)

    if update:
        gbp.log.info("Updating '%s': %s..%s" % (branch,
                                                repo.rev_parse(branch, short=12),
                                                repo.rev_parse(remote, short=12)))
        if repo.branch == branch:
            repo.merge(remote)
        else:
            sha1 = repo.rev_parse(remote)
            repo.update_ref("refs/heads/%s" % branch, sha1,
                            msg="gbp: forward %s to %s" % (branch, remote))
    return update


def build_parser(name):
    description = 'safely update a repository from remote'
    try:
        parser = GbpConfArgParserDebian.create_parser(prog=name,
                                                      description=description)
    except GbpError as err:
        gbp.log.err(err)
        return None

    branch_group = parser.add_argument_group("branch options", "branch update and layout options")

    branch_group.add_bool_conf_file_arg("--ignore-branch")
    branch_group.add_arg("--force", action="store_true",
                         help="force a branch update even if it can't be fast "
                              "forwarded")
    branch_group.add_arg("--all", action="store_true",
                         help="update all remote-tracking branches that "
                         "have identical name in the remote")
    branch_group.add_arg("--redo-pq", action="store_true",
                         help="redo the patch queue branch after a pull. Warning: "
                         "this drops the old patch-queue branch")
    branch_group.add_conf_file_arg("--upstream-branch")
    branch_group.add_conf_file_arg("--debian-branch")
    branch_group.add_bool_conf_file_arg("--pristine-tar")
    branch_group.add_bool_conf_file_arg("--track-missing", dest="track_missing")
    branch_group.add_arg("--depth", action="store", default=0,
                         help="git history depth (for deepening shallow clones)")
    parser.add_arg("-v", "--verbose", action="store_true",
                   help="verbose command execution")
    parser.add_conf_file_arg("--color", type='tristate')
    parser.add_conf_file_arg("--color-scheme")
    parser.add_argument("remote", metavar="REMOTE", nargs="?",
                        help="remote from which to pull")
    return parser


def parse_args(argv):
    parser = build_parser(os.path.basename(argv[0]))
    if not parser:
        return None
    return parser.parse_args(argv[1:])


def get_remote(repo, current):
    current_remote = repo.get_merge_branch(current)
    if current_remote:
        fetch_remote = current_remote.split('/')[0]
    else:
        fetch_remote = 'origin'
    return fetch_remote


def track_missing(repo, remote, branch, options):
    upstream = "remotes/{}/{}".format(remote, branch)
    if not repo.has_branch(branch):
        try:
            repo.fetch(remote, depth=options.depth, refspec=branch)
        except GitRepositoryError:
            pass  # it's o.k. if the remote branch is missing
        else:
            repo.create_branch(branch, upstream)


def main(argv):
    retval = 0
    current = None

    options = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    if options.remote:
        gbp.log.info("Fetching from '%s'" % options.remote)
    else:
        gbp.log.info("Fetching from default remote for each branch")

    try:
        repo = DebianGitRepository(os.path.curdir)
    except GitRepositoryError:
        gbp.log.err("%s is not a git repository" % (os.path.abspath('.')))
        return 1

    try:
        branches = set()
        try:
            current = repo.get_branch()
        except GitRepositoryError:
            # Not being on any branch is o.k. with --ignore-branch
            if options.ignore_branch:
                current = repo.head
                gbp.log.info("Found detached head at '%s'" % current)
            else:
                raise

        (ret, out) = repo.is_clean()
        if not ret:
            gbp.log.err("You have uncommitted changes in your source tree:")
            gbp.log.err(out)
            raise GbpError

        repo.fetch(options.remote, depth=options.depth)
        repo.fetch(options.remote, depth=options.depth, tags=True)

        fetch_remote = get_remote(repo, current)
        for branch in [options.debian_branch, options.upstream_branch]:
            if not branch:
                continue
            if options.track_missing:
                track_missing(repo, fetch_remote, branch, options)

            if repo.has_branch(branch):
                branches.add(branch)

        if options.pristine_tar:
            branch = repo.pristine_tar_branch
            if options.track_missing:
                track_missing(repo, fetch_remote, branch, options)

            if repo.has_pristine_tar_branch():
                branches.add(repo.pristine_tar_branch)

        if options.all:
            for branch in repo.get_local_branches():
                merge_branch = repo.get_merge_branch(branch)
                if merge_branch:
                    rem, rem_br = merge_branch.split('/', 1)
                    if rem == fetch_remote and branch == rem_br:
                        branches.add(branch)

        for branch in branches:
            if not fast_forward_branch(options.remote, branch, repo, options):
                retval = 2

        if options.redo_pq:
            repo.set_branch(options.debian_branch)
            Command("gbp-pq")(["drop"])
            Command("gbp-pq")(["import"])

        repo.set_branch(current)
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


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
