# vim: set fileencoding=utf-8 :
#
# (C) 2018 Shengjing Zhu <i@zhsj.me>
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
"""A Debian Copyright file"""
import email
import os


class NoCopyrightError(Exception):
    """No copyright found"""
    pass


class ParseCopyrightError(Exception):
    """Problem parsing copyright"""
    pass


class Copyright(object):
    """
    A Debian copyright
    """
    def __init__(self, contents=None, filename="debian/copyright"):
        """
        Parse an existing copyright file.

        @param contents: content of a control file
        @type contents: C{str}
        @param filename: name of the control file
        @type filename: C{str}
        @return: Copyright object
        @rtype: C{gbp.deb.copyright.Copyright} object
        """
        if contents:
            copyright = email.message_from_string(contents)
        else:
            if not os.access(filename, os.F_OK):
                raise NoCopyrightError("Copyright file %s doesn't exist" % filename)
            with open(filename) as f:
                copyright = email.message_from_file(f)

        if not copyright.items():
            raise ParseCopyrightError("Empty or invalid copyright file or contents")

        self._copyright = copyright
        self.filename = filename

    def files_excluded(self, component=None):
        """The file list to be excluded"""
        if component:
            files = self._copyright['Files-Excluded-' + component]
        else:
            files = self._copyright['Files-Excluded']
        if files:
            return files.split()
        else:
            return []
