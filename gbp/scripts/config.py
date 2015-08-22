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

from six.moves import configparser
import sys
import os, os.path
from gbp.config import GbpOptionParser
from gbp.scripts.supercommand import import_command
import gbp.log


def build_parser(name):
    try:
        parser = GbpOptionParser(command=os.path.basename(name), prefix='',
                             usage='%prog [options] command[.optionname] - display configuration settings')
    except configparser.ParsingError as err:
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


def parse_cmd_config(command):
    """Make a command parse it's config files"""
    parser = GbpOptionParser(command)
    parser.parse_config_files()
    return parser


def print_cmd_single_value(query, printer):
    """Print a single configuration value of a command

    @param query: the cmd to print the value for
    @param printer: the printer to output the value
    """
    try:
        cmd, option = query.split('.')
    except ValueError:
        return 2

    parser = parse_cmd_config(cmd)
    value = parser.get_config_file_value(option)
    if value is None:
        value = ''
    printer("%s=%s" % (query, value))
    return 0 if value else 1


def print_cmd_all_values(cmd, printer):
    """
    Print all configuration values of a command

    @param cmd: the cmd to print the values for
    @param printer: the printer to output the values
    """
    if not cmd:
        return 2
    try:
        # Populate the parser to get a list of
        # valid options
        module = import_command(cmd)
        parser = module.build_parser(cmd)
    except (AttributeError, ImportError):
        return 2

    for option in parser.valid_options:
        value = parser.get_config_file_value(option)
        if value != '':
            printer("%s.%s=%s" % (cmd, option, value))
    return 0


def value_printer(value):
    if (value):
        print(value)


def main(argv):
    retval = 1

    (options, args) = parse_args(argv)
    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    if not args:
        gbp.log.error("No command given")
        return 2
    elif len(args) != 2:
        gbp.log.error("Can only take a command or command.optionname, check --help")
        return 2
    else:
        query = args[1]

    if '.' in query:
        retval = print_cmd_single_value(query, value_printer)
    else:
        retval = print_cmd_all_values(query, value_printer)
    return retval

if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
