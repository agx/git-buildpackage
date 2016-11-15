#!/usr/bin/python
# vim: set fileencoding=utf-8 :
#
# (C) 2013 Guido Günther <agx@sigxcpu.org>
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
"""Supercommand for all gbp commands"""

from __future__ import print_function

import glob
import os
import re
import sys

# Command is this module and common/ is shared code
# so we don't allow these to be imported:
invalid_modules = ['common', 'supercommand']


def sanitize(cmd):
    """
    '-' is not allowed in module names
    so turn it into an underscore.
    """
    return cmd.replace('-', '_')


def usage():
    print("""
Usage:
    gbp <command> [<args>]

The most commonly used commands are:

    buildpackage - build a Debian package
    import-orig  - import a new upstream tarball
    import-dsc   - import a single Debian source package
    import-dscs  - import multiple Debian source packages

Use '--list-cmds' to list all available commands.
""")


def version(prog):
    try:
        from gbp.version import gbp_version
    except ImportError:
        gbp_version = '[Unknown version]'
    print("%s %s" % (os.path.basename(prog), gbp_version))


def import_command(cmd):
    """
    Import the module that implements the given command
    """
    modulename = sanitize(cmd)
    if (not re.match(r'[a-z][a-z0-9_]', modulename) or
            modulename in invalid_modules):
        raise ImportError('Illegal module name %s' % modulename)

    return __import__('gbp.scripts.%s' % modulename, fromlist='main', level=0)


def pymod_to_cmd(mod):
    """
    >>> pymod_to_cmd('/x/y/z/a_cmd.py')
    'a-cmd'
    """
    return os.path.basename(mod.rsplit('.', 1)[0]).replace('_', '-')


def get_available_commands(path):
    cmds = []
    for f in glob.glob(os.path.join(path, '*.py')):
        if os.path.basename(f) in ['__init__.py', 'supercommand.py']:
            continue
        cmds.append((pymod_to_cmd(f), f))
    return cmds


def list_available_commands():
    mod = __import__('gbp.scripts', fromlist='main', level=0)
    path = os.path.dirname(mod.__file__)
    maxlen = 0

    print("Available commands in %s\n" % path)
    cmds = sorted(get_available_commands(path))
    for cmd in cmds:
        if len(cmd[0]) > maxlen:
            maxlen = len(cmd[0])
    for cmd in cmds:
        mod = import_command(cmd[0])
        doc = mod.__doc__
        print("    %s - %s" % (cmd[0].rjust(maxlen), doc))
    print('')


def supercommand(argv=None):
    argv = argv or sys.argv

    if len(argv) < 2:
        usage()
        return 1

    prg, cmd = argv[0:2]
    args = argv[1:]

    if cmd in ['--help', '-h']:
        usage()
        return 0
    elif cmd == 'help' and len(args) > 1:
        # Make the first argument after help the new commadn and
        # request it's help output
        cmd = args[1]
        args = [cmd, '--help']
    elif cmd == 'help':
        usage()
        return 0
    elif cmd in ['--version', 'version']:
        version(argv[0])
        return 0
    elif cmd in ['--list-cmds', 'list-cmds']:
        list_available_commands()
        return 0

    try:
        module = import_command(cmd)
    except ImportError as e:
        print("'%s' is not a valid command." % cmd, file=sys.stderr)
        usage()
        if '--verbose' in args:
            print(e, file=sys.stderr)
        return 2

    return module.main(args)


if __name__ == '__main__':
    sys.exit(supercommand())

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
