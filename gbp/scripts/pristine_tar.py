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
#
"""Perform pristine-tar import into a Git repository"""

import os
import sys
import gbp.log
from gbp.command_wrappers import CommandExecFailed
from gbp.config import GbpOptionParserDebian
from gbp.deb.git import (GitRepositoryError, DebianGitRepository)
from gbp.deb.source import DebianSource
from gbp.errors import GbpError
from gbp.scripts.common import ExitCodes, get_component_tarballs


def usage_msg():
    return """%prog [action] [options] /path/to/upstream-version.tar.gz

Actions:
   commit         recreate the pristine-tar commits on the pristine-tar branch
"""


def build_parser(name):
    try:
        parser = GbpOptionParserDebian(command=os.path.basename(name), prefix='',
                                       usage=usage_msg())
    except GbpError as err:
        gbp.log.err(err)
        return None

    parser.add_config_file_option(option_name="upstream-tag",
                                  dest="upstream_tag")
    parser.add_config_file_option("component", action="append", metavar='COMPONENT',
                                  dest="components")
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
    ret = 1
    repo = None

    (options, args) = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    if len(args) != 2 or args[0] not in ['commit']:
        gbp.log.err("No action given")
        return 1
    else:
        tarball = args[1]

    try:
        try:
            repo = DebianGitRepository('.')
        except GitRepositoryError:
            raise GbpError("%s is not a git repository" % (os.path.abspath('.')))

        source = DebianSource('.')
        component_tarballs = get_component_tarballs(source.sourcepkg,
                                                    source.upstream_version,
                                                    tarball,
                                                    options.components)
        upstream_tag = repo.version_to_tag(options.upstream_tag,
                                           source.upstream_version)
        repo.create_pristine_tar_commits(upstream_tag,
                                         tarball,
                                         component_tarballs)
        ret = 0
    except (GitRepositoryError, GbpError, CommandExecFailed) as err:
        if str(err):
            gbp.log.err(err)
    except KeyboardInterrupt:
        gbp.log.err("Interrupted. Aborting.")

    if not ret:
        comp_msg = (' with additional tarballs for %s'
                    % ", ".join([os.path.basename(t[1]) for t in component_tarballs])) if component_tarballs else ''
        gbp.log.info("Successfully committed pristine-tar data for version %s of %s%s" % (source.upstream_version,
                                                                                          tarball,
                                                                                          comp_msg))
    return ret


if __name__ == "__main__":
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
