# vim: set fileencoding=utf-8 :
#
# (C) 2014 Guido Günther <agx@sigxcpu.org>
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
"""Query and display config file values"""

import sys
from gbp.config import GbpConfArgParser
from gbp.errors import GbpError
from gbp.scripts.supercommand import import_command
from gbp.scripts.common import ExitCodes
import gbp.log


def build_parser(name):
    description = 'display configuration settings'
    try:
        parser = GbpConfArgParser.create_parser(prog=name,
                                                description=description)
    except GbpError as err:
        gbp.log.err(err)
        return None

    parser.add_arg("-v", "--verbose", action="store_true",
                   help="verbose command execution")
    parser.add_conf_file_arg("--color", type='tristate')
    parser.add_conf_file_arg("--color-scheme")
    parser.add_argument("query", metavar="QUERY",
                        help="command[.optionname] to show")
    return parser


def parse_args(argv):
    parser = build_parser(argv[0])
    if not parser:
        return None
    return parser.parse_args(argv[1:])


def build_cmd_parser(section):
    """
    Populate the parser to get a list of valid options
    """
    try:
        # Populate the parser to get a list of
        # valid options
        module = import_command(section)
        parser = module.build_parser(section)
    except (AttributeError, ImportError):
        # Use the default parser for section that don't
        # map to a command
        parser = GbpConfArgParser.create_parser(prog=section)
    return parser


def print_single_option(parser, option, printer):
    try:
        value = parser.get_conf_file_value(option)
        printer("%s" % value)
        return 0
    except KeyError:
        return 2


def print_all_options(parser, printer):
    if not parser.conf_file_args:
        return 2
    for opt in parser.conf_file_args:
        value = parser.get_conf_file_value(opt)
        printer("%s.%s=%s" % (parser.command, opt, value))
    return 0


def print_cmd_values(query, printer):
    """
    Print configuration values of a command

    @param query: the section to print the values for or section.option to
        print
    @param printer: the printer to output the values
    """
    if not query:
        return 2

    try:
        section, option = query.split('.')
    except ValueError:
        section = query
        option = None

    parser = build_cmd_parser(section)

    if option:  # Single option query
        return print_single_option(parser, option, printer)
    else:  # all options
        return print_all_options(parser, printer)


def value_printer(output):
    print(output)


def main(argv):
    options = parse_args(argv)

    if options is None:
        return ExitCodes.parse_error

    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    return print_cmd_values(options.query, value_printer)


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
