# vim: set fileencoding=utf-8 :
#
# (C) 2017 Guido Günther <agx@sigxcpu.org>
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

import glob
import os

import gbp.command_wrappers as gbpc

from gbp.pkg.compressor import Compressor
from gbp.pkg.pkgpolicy import PkgPolicy

from gbp.errors import GbpError


class UpstreamSource(object):
    """
    Upstream source. Can be either an unpacked dir, a tarball or another type
    of archive

    @cvar _orig: are the upstream sources already suitable as an upstream
                 tarball
    @type _orig: boolean
    @cvar _path: path to the upstream sources
    @type _path: string
    @cvar _unpacked: path to the unpacked source tree
    @type _unpacked: string
    """
    def __init__(self, name, unpacked=None, pkg_policy=PkgPolicy):
        self._orig = False
        self._pkg_policy = pkg_policy
        self._path = name
        self.unpacked = unpacked

        self._check_orig()
        if self.is_dir():
            self.unpacked = self.path

    def _check_orig(self):
        """
        Check if upstream source format can be used as orig tarball.
        This doesn't imply that the tarball is correctly named.

        @return: C{True} if upstream source format is suitable
            as upstream tarball, C{False} otherwise.
        @rtype: C{bool}
        """
        if self.is_dir():
            self._orig = False
            return

        parts = self._path.split('.')
        try:
            if parts[-1] == 'tgz':
                self._orig = True
            elif parts[-2] == 'tar':
                if (parts[-1] in Compressor.Opts or
                        parts[-1] in Compressor.Aliases):
                    self._orig = True
        except IndexError:
            self._orig = False

    def is_orig(self):
        """
        @return: C{True} if sources are suitable as orig tarball,
            C{False} otherwise
        @rtype: C{bool}
        """
        return self._orig

    def is_dir(self):
        """
        @return: C{True} if if upstream sources are an unpacked directory,
            C{False} otherwise
        @rtype: C{bool}
        """
        return True if os.path.isdir(self._path) else False

    @property
    def path(self):
        return self._path.rstrip('/')

    def unpack(self, dir, filters=None):
        """
        Unpack packed upstream sources into a given directory
        (filtering out files specified by filters) and determine the
        toplevel of the source tree.
        """
        if self.is_dir():
            raise GbpError("Cannot unpack directory %s" % self.path)

        if not filters:
            filters = []

        if not isinstance(filters, list):
            raise GbpError("Filters must be a list")

        self._unpack_archive(dir, filters)
        self.unpacked = self._unpacked_toplevel(dir)

    def _unpack_archive(self, dir, filters):
        """
        Unpack packed upstream sources into a given directory
        allowing to filter out files in case of tar archives.
        """
        ext = os.path.splitext(self.path)[1]
        if ext in [".zip", ".xpi"]:
            if filters:
                raise GbpError("Can only filter tar archives: %s", (ext, self.path))
            self._unpack_zip(dir)
        else:
            self._unpack_tar(dir, filters)

    def _unpack_zip(self, dir):
        try:
            gbpc.UnpackZipArchive(self.path, dir)()
        except gbpc.CommandExecFailed:
            raise GbpError("Unpacking of %s failed" % self.path)

    def _unpacked_toplevel(self, dir):
        """unpacked archives can contain a leading directory or not"""
        unpacked = glob.glob('%s/*' % dir)
        unpacked.extend(glob.glob("%s/.*" % dir))  # include hidden files and folders
        # Check that dir contains nothing but a single folder:
        if len(unpacked) == 1 and os.path.isdir(unpacked[0]):
            return unpacked[0]
        else:
            return dir

    def _unpack_tar(self, dir, filters):
        """
        Unpack a tarball to I{dir} applying a list of I{filters}. Leave the
        cleanup to the caller in case of an error.
        """
        try:
            unpackArchive = gbpc.UnpackTarArchive(self.path, dir, filters)
            unpackArchive()
        except gbpc.CommandExecFailed:
            # unpackArchive already printed an error message
            raise GbpError

    def pack(self, newarchive, filters=None):
        """
        Recreate a new archive from the current one

        @param newarchive: the name of the new archive
        @type newarchive: string
        @param filters: tar filters to apply
        @type filters: array of strings
        @return: the new upstream source
        @rtype: UpstreamSource
        """
        if not self.unpacked:
            raise GbpError("Need an unpacked source tree to pack")

        if not filters:
            filters = []

        if not isinstance(filters, list):
            raise GbpError("Filters must be a list")

        try:
            unpacked = self.unpacked.rstrip('/')
            repackArchive = gbpc.PackTarArchive(newarchive,
                                                os.path.dirname(unpacked),
                                                os.path.basename(unpacked),
                                                filters)
            repackArchive()
        except gbpc.CommandExecFailed:
            # repackArchive already printed an error
            raise GbpError
        return type(self)(newarchive)

    @staticmethod
    def known_compressions():
        return Compressor.Exts.values()

    def guess_version(self, extra_regex=r''):
        return self._pkg_policy.guess_upstream_src_version(self.path,
                                                           extra_regex)
