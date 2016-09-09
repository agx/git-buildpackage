# vim: set fileencoding=utf-8 :
#
# (C) 2012 Daniel Dehennin <daniel.dehennin@baby-gnu.org>
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
"""A Debian Control file"""

import email
import os


class NoControlError(Exception):
    """No control found"""
    pass


class ParseControlError(Exception):
    """Problem parsing control"""
    pass


class Control(object):
    """A Debian control"""

    def __init__(self, contents=None, filename="debian/control"):
        """
        Parse an existing control file.

        @param contents: content of a control file
        @type contents: C{str}
        @param filename: name of the control file
        @type filename: C{str}
        @return: Control object
        @rtype: C{gbp.deb.conrol.Control} object
        """
        if contents:
            control = email.message_from_string(contents)
        else:
            if not os.access(filename, os.F_OK):
                raise NoControlError("Control file %s does not exist" % filename)

            with open(filename) as f:
                control = email.message_from_file(f)

        if not control.items():
            raise ParseControlError("Empty or invalid control file or contents")

        self._control = control
        self.filename = filename

    def __getitem__(self, item):
        return self._control[item]

    def __setitem__(self, item, value):
        self._control[item] = value

    @property
    def name(self):
        """The name of the package"""
        return self._control['Source']

    @property
    def section(self):
        """The section of the package"""
        return self._control['Section']

    @property
    def priority(self):
        """The priority of the package"""
        return self._control['Priority']
