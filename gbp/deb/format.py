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
#    along with this program; if not, please see
#    <http://www.gnu.org/licenses/>
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
    format_file = 'debian/source/format'

    def _parse(self, content):
        parts = content.split()

        self._version = parts[0]
        if len(parts) == 2:
            if (parts[1][0] == '(' and parts[1][-1] == ')'):
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

    def __str__(self):
        return "%s (%s)" % (self._version, self._type)

    @classmethod
    def parse_file(cls, filename):
        """
        Parse debian/source/format file

        @param filename: the file to parse
        @type filename: C{str}
        @returns: a debisn/source/format object
        @rtype: L{DebianSourceFormat}

        >>> from six import b
        >>> import tempfile, os
        >>> with tempfile.NamedTemporaryFile(delete=False) as t:
        ...    ret = t.write(b("3.0 (quilt)"))
        >>> d = DebianSourceFormat.parse_file(t.name)
        >>> d.version
        '3.0'
        >>> d.type
        'quilt'
        >>> os.unlink(t.name)
        """
        with open(filename) as f:
            return cls(f.read())

    @classmethod
    def from_content(cls, version, type, format_file=None):
        """
        Write a format file from I{type} and I{format} at
        I{format_file}

        @param version: the source package format version
        @param type: the format type
        @param format_file: the format file to create with
            the above parameters
        """
        format_file = format_file or cls.format_file
        with open(cls.format_file, 'w') as f:
            f.write("%s (%s)" % (version, type))
        return cls.parse_file(cls.format_file)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
