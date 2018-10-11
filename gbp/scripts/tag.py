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
"""Create a Debian tag"""

import os
import sys

import gbp.log
from gbp.format import format_str
from gbp.config import GbpConfArgParserDebian
from gbp.deb.git import DebianGitRepository, GitRepositoryError
from gbp.deb.source import DebianSourceError
from gbp.deb.source import DebianSource
from gbp.errors import GbpError

from gbp.scripts.common import ExitCodes
from gbp.scripts.common.hook import Hook

from gbp.scripts.common.pq import is_pq_branch, pq_branch_base


def create_debian_tag(repo, source, commit, options):
    """
    Create the debian tag

    returns: the created tag
    """
    tag = repo.version_to_tag(options.debian_tag, source.version)
    gbp.log.info("Tagging Debian package %s as %s in git" % (source.version, tag))
    if options.retag and repo.has_tag(tag):
        repo.delete_tag(tag)
    tag_msg = format_str(options.debian_tag_msg,
                         dict(pkg=source.sourcepkg,
                              version=source.version))
    repo.create_tag(name=tag,
                    msg=tag_msg,
                    sign=options.sign_tags,
                    commit=commit,
                    keyid=options.keyid)
    return tag


def perform_tagging(repo, source, options, hook_env=None):
    """
    Perform the tagging

    Select brach to tag, create tag and run hooks
    """
    branch = repo.branch
    if branch and is_pq_branch(branch):
        commit = repo.get_merge_base(branch, pq_branch_base(branch))
    else:
        commit = repo.head

    tag = create_debian_tag(repo, source, commit, options)
    if options.posttag:
        sha = repo.rev_parse("%s^{}" % tag)
        Hook('Posttag', options.posttag,
             extra_env=Hook.md(hook_env or {},
                               {'GBP_TAG': tag,
                                'GBP_BRANCH': branch or '(no branch)',
                                'GBP_SHA1': sha})
             )()


def build_parser(name):
    try:
        parser = GbpConfArgParserDebian.create_parser(prog=name)
    except GbpError as err:
        gbp.log.err(err)
        return None

    parser.add_arg("--retag", action="store_true",
                   help="don't fail if the tag already exists")
    parser.add_conf_file_arg("--debian-branch")
    parser.add_conf_file_arg("--debian-tag")
    parser.add_conf_file_arg("--debian-tag-msg")
    parser.add_bool_conf_file_arg("--sign-tags")
    parser.add_conf_file_arg("--keyid")
    parser.add_conf_file_arg("--posttag",
                             help="hook run after a successful tag operation")
    parser.add_bool_conf_file_arg("--ignore-branch")
    parser.add_bool_conf_file_arg("--ignore-new")
    parser.add_conf_file_arg("--color", type='tristate')
    parser.add_conf_file_arg("--color-scheme")
    parser.add_arg("--verbose", action="store_true",
                   help="verbose command execution")
    return parser


def parse_args(argv):
    parser = build_parser(os.path.basename(argv[0]))
    if not parser:
        return None
    return parser.parse_args(argv[1:])


def main(argv):
    retval = 1

    options = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    gbp.log.setup(options.color, options.verbose, options.color_scheme)
    try:
        repo = DebianGitRepository(os.path.curdir, toplevel=False)
    except GitRepositoryError:
        gbp.log.err("%s is not inside a git repository" % (os.path.abspath('.')))
        return 1

    try:
        source = DebianSource(repo.path)
        if not (options.ignore_branch or options.ignore_new):
            if repo.branch != options.debian_branch:
                gbp.log.err("You are not on branch '%s' but on '%s'"
                            % (options.debian_branch,
                               repo.branch or 'no branch'))
                raise GbpError("Use --ignore-branch to ignore or "
                               "--debian-branch to set the branch name.")

        if not options.ignore_new:
            (ret, out) = repo.is_clean()
            if not ret:
                gbp.log.err("You have uncommitted changes in your source tree:")
                gbp.log.err(out)
                raise GbpError("Use --ignore-new to ignore.")

        perform_tagging(repo, source, options)
        retval = 0
    except (GbpError, GitRepositoryError, DebianSourceError) as err:
        if str(err):
            gbp.log.err(err)
    except KeyboardInterrupt:
        gbp.log.err("Interrupted. Aborting.")

    return retval


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
