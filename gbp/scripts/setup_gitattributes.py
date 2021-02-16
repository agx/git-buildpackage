# vim: set fileencoding=utf-8 :
#
# (C) 2021 Andrej Shadura <andrew@shadura.me>
# (C) 2021 Collabora Limited
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
"""Setup Git attributes to incapacitate .gitattributes shipped by the upstream"""

import os
import sys
import gbp.log
from gbp.command_wrappers import CommandExecFailed
from gbp.config import GbpOptionParserDebian
from gbp.deb.git import GitRepositoryError, DebianGitRepository
from gbp.errors import GbpError
from gbp.scripts.common import ExitCodes
from gbp.scripts.common.repo_setup import setup_gitattributes


def build_parser(name):
    setting_presets = {'dgit-defuse-attrs'}

    def disable_preset(option, opt, value, parser):
        setting = opt.replace('--no-', '')
        if parser.values.attr_presets and setting in parser.values.attr_presets:
            parser.values.attr_presets.remove(setting)

    def enable_preset(option, opt, value, parser):
        setting = opt.replace('--', '')
        parser.values.attr_presets.add(setting)

    try:
        parser = GbpOptionParserDebian(command=os.path.basename(name), prefix='',
                                       usage='%prog - set up sane Git attributes')
    except GbpError as err:
        gbp.log.err(err)
        return None

    parser.add_option("--verbose", action="store_true", dest="verbose",
                      default=False, help="verbose command execution")
    for preset in setting_presets:
        parser.add_option("--%s" % preset, action="callback", callback=enable_preset,
                          help="Apply %s preset" % preset)
        parser.add_option("--no-%s" % preset, action="callback", callback=disable_preset,
                          help="Do not apply %s preset" % preset)
    parser.add_option("--all", action="store_const", dest="attr_presets",
                      const=setting_presets, default=setting_presets, help="apply all known settings")
    parser.add_config_file_option(option_name="color", dest="color",
                                  type='tristate')
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
    repo = None

    (options, args) = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    try:
        try:
            repo = DebianGitRepository('.')
        except GitRepositoryError:
            raise GbpError("%s is not a git repository" % (os.path.abspath('.')))

        if not options.attr_presets:
            raise GbpError("Nothing to do, no settings to apply.")
        setup_gitattributes(repo)
    except (GitRepositoryError, GbpError, CommandExecFailed) as err:
        if str(err):
            gbp.log.err(err)
    except KeyboardInterrupt:
        gbp.log.err("Interrupted. Aborting.")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
