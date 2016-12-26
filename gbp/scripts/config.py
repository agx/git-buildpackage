# vim: set fileencoding=utf-8 :
#
# (C) 2014 Guido Guenther <agx@sigxcpu.org>
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
import os
from gbp.config import GbpOptionParser
from gbp.errors import GbpError
from gbp.scripts.supercommand import import_command
from gbp.scripts.common import ExitCodes
import gbp.log


def build_parser(name):
    try:
        parser = GbpOptionParser(command=os.path.basename(name), prefix='',
                                 usage='%prog [options] command[.optionname] - display configuration settings')
    except GbpError as err:
        gbp.log.err(err)
        return None

    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    return parser


def parse_args(argv):
    parser = build_parser(argv[0])
    if not parser:
        return None, None
    return parser.parse_args(argv)


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
        parser = GbpOptionParser(section)
        parser.parse_config_files()
    return parser


def print_single_option(parser, option, printer):
    value = parser.get_config_file_value(option)
    if value is not None:
        printer("%s.%s=%s" % (parser.command, option, value))
    else:
        return 2
    return 0


def print_all_options(parser, printer):
    if not parser.valid_options:
        return 2
    for opt in parser.valid_options:
        value = parser.get_config_file_value(opt)
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
    retval = 1

    (options, args) = parse_args(argv)

    if options is None:
        return ExitCodes.parse_error

    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    if not args:
        gbp.log.err("No command given")
        return 2
    elif len(args) != 2:
        gbp.log.err("Can only take a command or command.optionname, check --help")
        return 2
    else:
        query = args[1]

    retval = print_cmd_values(query, value_printer)
    return retval


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
