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
"""provides some debian source package related helpers"""

import os
from gbp.deb.format import DebianSourceFormat
from gbp.deb.changelog import ChangeLog

import six


class FileVfs(object):
    def __init__(self, dir):
        """
        Access files in a unpaced Debian source package.

        @param dir: the toplevel of the source tree
        @type dir: C{str}
        """
        self._dir = dir

    def open(self, path, flags=None):
        flags = flags or 'r'
        return open(os.path.join(self._dir, path), flags)


class DebianSourceError(Exception):
    pass


class DebianSource(object):
    """
    A debianized source tree

    Querying/setting information in a debianized source tree
    involves several files. This class provides a common interface.
    """
    def __init__(self, vfs):
        """
        @param vfs: a class that implemented GbpVFS interfacce or
             a directory (which will used the DirGbpVFS class.
        """
        self._changelog = None

        if isinstance(vfs, six.string_types):
            self._vfs = FileVfs(vfs)
        else:
            self._vfs = vfs

    def is_native(self):
        """
        Whether this is a native Debian package
        """
        try:
            ff = self._vfs.open('debian/source/format')
            f = DebianSourceFormat(ff.read())
            if f.type:
                return f.type == 'native'
        except IOError as e:
            pass  # Fall back to changelog parsing

        try:
            return '-' not in self.changelog.version
        except IOError as e:
            raise DebianSourceError("Failed to determine source format: %s" % e)

    @property
    def changelog(self):
        """
        Return the L{gbp.deb.ChangeLog}
        """
        if not self._changelog:
            try:
                clf = self._vfs.open('debian/changelog')
                self._changelog = ChangeLog(clf.read())
            except IOError as err:
                raise DebianSourceError('Failed to read changelog: %s' % err)
        return self._changelog

    @property
    def sourcepkg(self):
        """
        The source package's name
        """
        return self.changelog['Source']
