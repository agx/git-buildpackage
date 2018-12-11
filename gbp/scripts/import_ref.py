# vim: set fileencoding=utf-8 :
#
# (C) 2018 Michael Stapelberg <stapelberg@debian.org>
#     2018 Guido Günther <agx@sigxcpu.org>
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
"""Import a new upstream version from a git branch onto the Debian branch"""

import os
import sys
import gbp.command_wrappers as gbpc
from gbp.deb.git import GitRepositoryError
from gbp.config import GbpOptionParserDebian, GbpOptionGroup
from gbp.errors import GbpError
import gbp.log
from gbp.scripts.common import ExitCodes
from gbp.deb.rollbackgit import RollbackDebianGitRepository

from gbp.scripts.import_orig import (debian_branch_merge,
                                     postimport_hook,
                                     set_bare_repo_options,
                                     rollback)


def get_commit_and_version_to_merge(repo, options):
    """
    Get the commit and version we want to merge based on the
    --upstream-tag setting
    """
    version = options.version
    if options.upstream_tree.upper() == 'VERSION':
        # Determine tag name from given version
        if not options.version:
            raise GbpError("No upstream version given, try -u<version>")
        commit = repo.version_to_tag(options.upstream_tag, options.version)
    elif options.upstream_tree.upper() == 'BRANCH':
        # Use head of upstrem branch
        if not repo.has_branch(options.upstream_branch):
            raise GbpError("%s is not a valid branch" % options.upstream_branch)
        commit = options.upstream_branch
    else:
        # Use whatever is passed in as commitish
        commit = "%s^{commit}" % options.upstream_tree
    return commit, version


def build_parser(name):
    try:
        parser = GbpOptionParserDebian(command=os.path.basename(name), prefix='',
                                       usage='%prog [options] /path/to/upstream-version.tar.gz | --uscan')
    except GbpError as err:
        gbp.log.err(err)
        return None

    import_group = GbpOptionGroup(parser, "import options",
                                  "import related options")
    tag_group = GbpOptionGroup(parser, "tag options",
                               "tag related options ")
    branch_group = GbpOptionGroup(parser, "version and branch naming options",
                                  "version number and branch layout options")
    cmd_group = GbpOptionGroup(parser, "external command options",
                               "how and when to invoke external commands and hooks")
    for group in [import_group, branch_group, tag_group, cmd_group]:
        parser.add_option_group(group)

    branch_group.add_option("-u", "--upstream-version", dest="version",
                            help="The version number to use for the new version, "
                            "default is ''", default='')
    branch_group.add_config_file_option(option_name="debian-branch",
                                        dest="debian_branch")
    branch_group.add_config_file_option(option_name="upstream-branch",
                                        dest="upstream_branch")
    branch_group.add_config_file_option(option_name="upstream-tree",
                                        dest="upstream_tree",
                                        help="Where to merge the upstream changes from.",
                                        default="VERSION")
    branch_group.add_config_file_option(option_name="merge-mode", dest="merge_mode")

    tag_group.add_boolean_config_file_option(option_name="sign-tags",
                                             dest="sign_tags")
    tag_group.add_config_file_option(option_name="keyid",
                                     dest="keyid")
    tag_group.add_config_file_option(option_name="upstream-tag",
                                     dest="upstream_tag")
    import_group.add_config_file_option(option_name="import-msg",
                                        dest="import_msg")
    cmd_group.add_config_file_option(option_name="postimport", dest="postimport")

    parser.add_boolean_config_file_option(option_name="rollback",
                                          dest="rollback")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    return parser


def parse_args(argv):
    """Parse the command line arguments
    @return: options and arguments
    """

    parser = build_parser(argv[0])
    if not parser:
        return None, None

    (options, args) = parser.parse_args(argv[1:])
    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    return options, args


def main(argv):
    ret = 0
    repo = None

    (options, args) = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    # TODO: honor --filter option
    # TODO: add --filter-with-copyright which takes d/copyright into account
    # TODO: handle automatic versions based on timestamp + sha1
    # TODO: handle updating of upstream branch from remote
    gbp.log.warn("This script is experimental, it might change incompatibly between versions.")
    try:
        try:
            repo = RollbackDebianGitRepository('.')
        except GitRepositoryError:
            raise GbpError("%s is not a git repository" % (os.path.abspath('.')))

        commit, version = get_commit_and_version_to_merge(repo, options)

        is_empty = repo.is_empty()

        (clean, out) = repo.is_clean()
        if not clean and not is_empty:
            gbp.log.err("Repository has uncommitted changes, commit these first: ")
            raise GbpError(out)

        if repo.bare:
            set_bare_repo_options(options)

        try:
            tag = repo.version_to_tag(options.upstream_tag, version)
            if not repo.has_tag(tag):
                gbp.log.info("Upstream tag '%s' not found. Creating it for you." % tag)
                repo.create_tag(name=tag,
                                msg="Upstream version %s" % version,
                                commit="%s^0" % commit,
                                sign=options.sign_tags,
                                keyid=options.keyid)

            if is_empty:
                repo.create_branch(branch=options.debian_branch, rev=commit)
                repo.force_head(options.debian_branch, hard=True)
                # In an empty repo avoid master branch defaulted to by
                # git and check out debian branch instead.
                if not repo.bare:
                    cur = repo.branch
                    if cur != options.debian_branch:
                        repo.set_branch(options.debian_branch)
                        repo.delete_branch(cur)
            else:
                repo.rrr_branch(options.debian_branch)
                debian_branch_merge(repo, tag, version, options)

            # Update working copy and index if we've possibly updated the
            # checked out branch
            current_branch = repo.get_branch()
            if current_branch in [options.upstream_branch,
                                  repo.pristine_tar_branch]:
                repo.force_head(current_branch, hard=True)

            postimport_hook(repo, tag, version, options)
        except (gbpc.CommandExecFailed, GitRepositoryError) as err:
            msg = str(err) or 'Unknown error, please report a bug'
            raise GbpError("Import of %s failed: %s" % (commit, msg))
        except KeyboardInterrupt:
            raise GbpError("Import of %s failed: aborted by user" % (options.git_ref))
    except GbpError as err:
        if str(err):
            gbp.log.err(err)
        ret = 1
        rollback(repo, options)

    if not ret:
        gbp.log.info("Successfully imported version %s" % (version))
    return ret


if __name__ == "__main__":
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
