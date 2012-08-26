# vim: set fileencoding=utf-8 :
#
# (C) 2012 Guido Günther <agx@sigxcpu.org>
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
"""Parse debian/source/format"""

class DebianSourceFormatError(Exception):
    pass

class DebianSourceFormat(object):
    """
    Contents of debian/source/format

    >>> d = DebianSourceFormat("3.0 (quilt)")
    >>> d.type
    'quilt'
    >>> d.version
    '3.0'
    >>> d = DebianSourceFormat("3.0 (native)")
    >>> d.type
    'native'
    >>> d = DebianSourceFormat("1.0")
    >>> d.type
    >>> d.version
    '1.0'
    >>> d = DebianSourceFormat("1.0 broken")
    Traceback (most recent call last):
    ...
    DebianSourceFormatError: Cannot get source format from '1.0 broken'
    """

    def _parse(self, content):
        parts = content.split()

        self._version = parts[0]
        if len(parts) == 2:
            if (parts[1][0] == '(' and
                parts[1][-1] == ')'):
                self._type = parts[1][1:-1]
            else:
                raise DebianSourceFormatError("Cannot get source format from "
                                              "'%s'" % content)

    def __init__(self, content):
        self._version = None
        self._type = None
        self._parse(content)

    @property
    def version(self):
        """The source format version number"""
        return self._version

    @property
    def type(self):
        """The 'type' (e.g. git, native)"""
        return self._type

    @classmethod
    def parse_file(klass, filename):
        """
        Parse debian/source/format file

        @param filename: the file to parse
        @type filename: C{str}
        @returns: a debisn/source/format object
        @rtype: L{DebianSourceFormat}

        >>> import tempfile, os
        >>> with tempfile.NamedTemporaryFile(delete=False) as t:
        ...    t.write("3.0 (quilt)")
        >>> d = DebianSourceFormat.parse_file(t.name)
        >>> d.version
        '3.0'
        >>> d.type
        'quilt'
        >>> os.unlink(t.name)
        """
        with file(filename) as f:
            return klass(f.read())


if __name__ == "__main__":
    import doctest
    doctest.testmod()
