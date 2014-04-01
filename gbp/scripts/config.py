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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""Query and display config file values"""

import ConfigParser
import sys
import os, os.path
from gbp.config import (GbpOptionParser, GbpOptionGroup)
from gbp.errors import GbpError
import gbp.log

def parse_args(argv):
    try:
        parser = GbpOptionParser(command=os.path.basename(argv[0]), prefix='',
                             usage='%prog [options] - display configuration settings')
    except ConfigParser.ParsingError as err:
        gbp.log.err(err)
        return None, None

    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    return parser.parse_args(argv)


def parse_config(command):
    parser = GbpOptionParser(command)
    parser.parse_config_files()
    return parser


def print_single_value(query, printer):
    try:
        cmd, option = query.split('.')
    except ValueError:
        return 2

    parser = parse_config(cmd)
    value = parser.get_config_file_value(option)
    printer(value)
    return 0 if value else 1


def single_value_printer(value):
    if (value):
        print(value)


def main(argv):
    retval = 0

    (options, args) = parse_args(argv)
    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    if not args:
        gbp.log.error("No command given")
        return 2
    elif len(args) != 2:
        gbp.log.error("Can only print a single value")
        return 2
    else:
        query = args[1]

    retval = print_single_value(query, single_value_printer)
    return retval

if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
