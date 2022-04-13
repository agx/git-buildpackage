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
from gbp.deb import DebianPkgPolicy as Policy
from gbp.deb.format import DebianSourceFormat
from gbp.deb.changelog import ChangeLog
from gbp.deb.control import Control
from gbp.deb.copyright import Copyright


class FileVfs(object):
    def __init__(self, dir):
        """
        Access files in an unpacked Debian source package.

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
        @param vfs: a class that implements L{GitVfs} interface or a directory
            (which will use the L{FileVfs} class. The directory must be the
            toplevel of a Debian source package.
        """
        self._changelog = None
        self._control = None
        self._copyright = None

        if isinstance(vfs, str):
            self._vfs = FileVfs(vfs)
        else:
            self._vfs = vfs

    def is_native(self):
        """
        Whether this is a native Debian package
        """
        try:
            with self._vfs.open('debian/source/format') as ff:
                f = DebianSourceFormat(ff.read())
            if f.type:
                return f.type == 'native'
        except IOError:
            pass  # Fall back to changelog parsing

        try:
            return '-' not in self.changelog.version
        except IOError as e:
            raise DebianSourceError("Failed to determine source format: %s" % e)

    def is_releasable(self):
        """
        Check if package is releasable

        Debian's current practice is to check for UNRELEASED in the distribution.
        """
        return self.changelog.distribution != 'UNRELEASED'

    @property
    def changelog(self):
        """
        Return the L{gbp.deb.ChangeLog}
        """
        if not self._changelog:
            try:
                with self._vfs.open('debian/changelog', 'rb') as clf:
                    self._changelog = ChangeLog(clf.read().decode('utf-8'))
            except IOError as err:
                raise DebianSourceError('Failed to read changelog: %s' % err)
        return self._changelog

    @property
    def control(self):
        """
        Return the L{gbp.deb.Control}
        """
        if not self._control:
            try:
                with self._vfs.open('debian/control', 'rb') as cf:
                    self._control = Control(cf.read().decode('utf-8'))
            except IOError as err:
                raise DebianSourceError('Failed to read control file: %s' % err)
        return self._control

    @property
    def copyright(self):
        """
        Return the L{gbp.deb.copyright}
        """
        if not self._copyright:
            try:
                with self._vfs.open('debian/copyright', 'rb') as crf:
                    self._copyright = Copyright(crf.read().decode('utf-8'))
            except IOError as err:
                raise DebianSourceError('Failed to read copyright file: %s' % err)
        return self._copyright

    @property
    def sourcepkg(self):
        """
        The source package's name
        """
        return self.changelog['Source']

    @property
    def name(self):
        return self.sourcepkg

    @property
    def version(self):
        return self.changelog.version

    @property
    def upstream_version(self):
        return self.changelog.upstream_version

    @property
    def debian_version(self):
        return self.changelog.debian_version

    def upstream_tarball_name(self, compression, component=None):
        """
        Possible upstream tarball name for this source package

        Gives the name of the main tarball if component is None
        """
        if self.is_native():
            return None
        return Policy.build_tarball_name(self.name,
                                         self.upstream_version,
                                         compression=compression,
                                         component=component)

    def upstream_tarball_names(self, comp_type, components=None):
        """
        Possible upstream tarballs names for this source package

        This includes component tarballs names.  with the given
        component names
        """
        names = [self.upstream_tarball_name(comp_type)]
        names += [self.upstream_tarball_name(comp_type, c) for c in (components or [])]
        return names
