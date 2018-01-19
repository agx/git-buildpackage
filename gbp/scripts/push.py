#!/usr/bin/python3
# vim: set fileencoding=utf-8 :
#
# (C) 2017 Guido Günther <agx@sigxcpu.org>
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
"""Push your changes to a remote"""

import os
import sys

import gbp.log
from gbp.config import GbpOptionParserDebian
from gbp.deb.git import DebianGitRepository, GitRepositoryError
from gbp.deb.source import DebianSourceError
from gbp.deb.source import DebianSource
from gbp.errors import GbpError
from gbp.scripts.common import ExitCodes


def build_parser(name):
    try:
        parser = GbpOptionParserDebian(command=os.path.basename(name),
                                       usage='%prog [options]')
    except GbpError as err:
        gbp.log.err(err)
        return None

    parser.add_option("-d", "--dry-run", dest="dryrun", default=False,
                      action="store_true", help="dry run, don't push.")
    parser.add_config_file_option(option_name="upstream-branch",
                                  dest="upstream_branch")
    parser.add_config_file_option(option_name="upstream-tag",
                                  dest="upstream_tag")
    parser.add_config_file_option(option_name="debian-branch",
                                  dest="debian_branch")
    parser.add_config_file_option(option_name="debian-tag",
                                  dest="debian_tag")
    parser.add_boolean_config_file_option(option_name="pristine-tar",
                                          dest="pristine_tar")
    parser.add_boolean_config_file_option(option_name="ignore-branch", dest="ignore_branch")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    parser.add_option("--verbose", action="store_true", dest="verbose",
                      default=False, help="verbose command execution")
    return parser


def parse_args(argv):
    parser = build_parser(argv[0])
    if not parser:
        return None, None
    return parser.parse_args(argv)


def do_push(repo, dests, to_push, dry_run):
    verb = "Dry-run: Pushing" if dry_run else "Pushing"
    success = True
    for dest in dests:
        for tag in to_push['tags']:
            gbp.log.info("%s %s to %s" % (verb, tag, dest))
            try:
                repo.push_tag(dest, tag, dry_run=dry_run)
            except GitRepositoryError as e:
                gbp.log.err(e)
                success = False
        for k, v in to_push['refs'].items():
            gbp.log.info("%s %s to %s:%s" % (verb, v, dest, k))
            try:
                repo.push(dest, v, k, dry_run=dry_run)
            except GitRepositoryError as e:
                gbp.log.err(e)
                success = False
    return success


def get_push_src(repo, ref, tag):
    """
    Determine wether we can push the ref

    If the ref is further ahead than the tag
    we only want to push up to this tag.
    """
    commit = repo.rev_parse("%s^{commit}" % tag)
    if repo.rev_parse(ref) == commit:
        return ref
    else:
        return commit


def get_remote(repo, branch):
    remote_branch = repo.get_merge_branch(branch)
    return remote_branch.split('/')[0] if remote_branch else 'origin'


def main(argv):
    retval = 1
    branch = None
    dest = None
    to_push = {
        'refs': {},
        'tags': [],
    }

    (options, args) = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    if len(args) > 2:
        gbp.log.err("Only a single remote repository can be given")
    elif len(args) == 2:
        dest = args[1]

    gbp.log.setup(options.color, options.verbose, options.color_scheme)
    try:
        repo = DebianGitRepository(os.path.curdir, toplevel=False)
    except GitRepositoryError:
        gbp.log.err("%s is not inside a git repository" % (os.path.abspath('.')))
        return 1

    try:
        source = DebianSource(repo.path)
        branch = repo.branch
        if not options.ignore_branch:
            if branch != options.debian_branch:
                gbp.log.err("You are not on branch '%s' but %s" %
                            (options.debian_branch,
                             "on '%s'" % branch if branch else 'in detached HEAD state'))
                raise GbpError("Use --ignore-branch to ignore or --debian-branch to set the branch name.")

        if not dest:
            dest = get_remote(repo, branch)

        dtag = repo.version_to_tag(options.debian_tag, source.version)
        if repo.has_tag(dtag):
            to_push['tags'].append(dtag)
            if source.is_releasable() and branch:
                ref = 'refs/heads/%s' % branch
                to_push['refs'][ref] = get_push_src(repo, ref, dtag)

        if not source.is_native():
            utag = repo.version_to_tag(options.upstream_tag,
                                       source.upstream_version)
            if repo.has_tag(utag):
                to_push['tags'].append(utag)
                ref = 'refs/heads/%s' % options.upstream_branch
                to_push['refs'][ref] = get_push_src(repo, ref, utag)

            if options.pristine_tar:
                commit = repo.get_pristine_tar_commit(source)
                if commit:
                    ref = 'refs/heads/pristine-tar'
                    to_push['refs'][ref] = get_push_src(repo, ref, commit)

        if do_push(repo, [dest], to_push, dry_run=options.dryrun):
            retval = 0
        else:
            gbp.log.err("Failed to push some refs.")
            retval = 1
    except (GbpError, GitRepositoryError, DebianSourceError) as err:
        if str(err):
            gbp.log.err(err)
    except KeyboardInterrupt:
        gbp.log.err("Interrupted. Aborting.")

    return retval


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
