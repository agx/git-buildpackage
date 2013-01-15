# vim: set fileencoding=utf-8 :
#
# (C) 2009,2010 Guido Guenther <agx@sigxcpu.org>
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
# inspired by dom-git-checkout
#
"""clone a repo and set it up for gbp"""

import sys
import os, os.path
from gbp.config import (GbpOptionParser, GbpOptionGroup)
from gbp.deb.git import DebianGitRepository
from gbp.git import (GitRepository, GitRepositoryError)
from gbp.errors import GbpError
import gbp.log


def parse_args (argv):
    parser = GbpOptionParser(command=os.path.basename(argv[0]), prefix='',
                             usage='%prog [options] repository - clone a remote repository')
    branch_group = GbpOptionGroup(parser, "branch options", "branch tracking and layout options")
    parser.add_option_group(branch_group)

    branch_group.add_option("--all", action="store_true", dest="all", default=False,
                            help="track all branches, not only debian and upstream")
    branch_group.add_config_file_option(option_name="upstream-branch", dest="upstream_branch")
    branch_group.add_config_file_option(option_name="debian-branch", dest="debian_branch")
    branch_group.add_boolean_config_file_option(option_name="pristine-tar", dest="pristine_tar")
    branch_group.add_option("--depth", action="store", dest="depth", default=0,
                            help="git history depth (for creating shallow clones)")

    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")

    (options, args) = parser.parse_args(argv)
    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    return (options, args)


def main(argv):
    retval = 0

    (options, args) = parse_args(argv)

    if len(args) != 2:
        gbp.log.err("Need a repository to clone.")
        return 1
    else:
        source = args[1]

    try:
        GitRepository(os.path.curdir)
        gbp.log.err("Can't run inside a git repository.")
        return 1
    except GitRepositoryError:
        pass

    try:
        repo = DebianGitRepository.clone(os.path.curdir, source, options.depth)
        os.chdir(repo.path)

        # Reparse the config files of the cloned repository so we pick up the
        # branch information from there:
        (options, args) = parse_args(argv)

        # Track all branches:
        if options.all:
            remotes = repo.get_remote_branches()
            for remote in remotes:
                local = remote.replace("origin/", "", 1)
                if not repo.has_branch(local) and \
                    local != "HEAD":
                        repo.create_branch(local, remote)
        else: # only track gbp's default branches
            branches = [ options.debian_branch, options.upstream_branch ]
            if options.pristine_tar:
                branches += [ repo.pristine_tar_branch ]
            gbp.log.debug('Will track branches: %s' % branches)
            for branch in branches:
                remote = 'origin/%s' % branch
                if repo.has_branch(remote, remote=True) and \
                    not repo.has_branch(branch):
                        repo.create_branch(branch, remote)

        repo.set_branch(options.debian_branch)

    except GitRepositoryError as err:
        gbp.log.err("Git command failed: %s" % err)
        retval = 1
    except GbpError as err:
        if len(err.__str__()):
            gbp.log.err(err)
        retval = 1

    return retval

if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
