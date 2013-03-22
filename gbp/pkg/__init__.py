# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
# (C) 2012 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""Common functionality of the Debian/RPM package helpers"""

import os
import re
import glob

import gbp.command_wrappers as gbpc
from gbp.errors import GbpError

# compression types, extra options and extensions
compressor_opts = { 'gzip'  : [ '-n', 'gz' ],
                    'bzip2' : [ '', 'bz2' ],
                    'lzma'  : [ '', 'lzma' ],
                    'xz'    : [ '', 'xz' ] }

# Map frequently used names of compression types to the internal ones:
compressor_aliases = { 'bz2' : 'bzip2',
                       'gz'  : 'gzip', }

class PkgPolicy(object):
    """
    Common helpers for packaging policy.
    """
    packagename_re = None
    packagename_msg = None
    upstreamversion_re = None
    upstreamversion_msg = None

    @classmethod
    def is_valid_packagename(cls, name):
        """
        Is this a valid package name?

        >>> PkgPolicy.is_valid_packagename('doesnotmatter')
        Traceback (most recent call last):
        ...
        NotImplementedError: Class needs to provide packagename_re
        """
        if cls.packagename_re is None:
            raise NotImplementedError("Class needs to provide packagename_re")
        return True if cls.packagename_re.match(name) else False

    @classmethod
    def is_valid_upstreamversion(cls, version):
        """
        Is this a valid upstream version number?

        >>> PkgPolicy.is_valid_upstreamversion('doesnotmatter')
        Traceback (most recent call last):
        ...
        NotImplementedError: Class needs to provide upstreamversion_re
        """
        if cls.upstreamversion_re is None:
            raise NotImplementedError("Class needs to provide upstreamversion_re")
        return True if cls.upstreamversion_re.match(version) else False

    @staticmethod
    def get_compression(orig_file):
        """
        Given an orig file return the compression used

        >>> PkgPolicy.get_compression("abc.tar.gz")
        'gzip'
        >>> PkgPolicy.get_compression("abc.tar.bz2")
        'bzip2'
        >>> PkgPolicy.get_compression("abc.tar.foo")
        >>> PkgPolicy.get_compression("abc")
        """
        try:
            ext = orig_file.rsplit('.',1)[1]
        except IndexError:
            return None
        for (c, o) in compressor_opts.iteritems():
            if o[1] == ext:
                return c
        return None

    @staticmethod
    def has_orig(orig_file, dir):
        "Check if orig tarball exists in dir"
        try:
            os.stat( os.path.join(dir, orig_file) )
        except OSError:
            return False
        return True

    @staticmethod
    def symlink_orig(orig_file, orig_dir, output_dir, force=False):
        """
        symlink orig tarball from orig_dir to output_dir
        @return: True if link was created or src == dst
                 False in case of error or src doesn't exist
        """
        orig_dir = os.path.abspath(orig_dir)
        output_dir = os.path.abspath(output_dir)

        if orig_dir == output_dir:
            return True

        src = os.path.join(orig_dir, orig_file)
        dst = os.path.join(output_dir, orig_file)
        if not os.access(src, os.F_OK):
            return False
        try:
            if os.access(dst, os.F_OK) and force:
                os.unlink(dst)
            os.symlink(src, dst)
        except OSError:
            return False
        return True


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
    def __init__(self, name, unpacked=None):
        self._orig = False
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
                if (parts[-1] in compressor_opts or
                    parts[-1] in compressor_aliases):
                        self._orig = True
        except IndexError:
            self._orig = False

    def is_orig(self):
        """
        @return: C{True} if sources are suitable as upstream source,
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

    def unpack(self, dir, filters=[]):
        """
        Unpack packed upstream sources into a given directory
        and determine the toplevel of the source tree.
        """
        if self.is_dir():
            raise GbpError("Cannot unpack directory %s" % self.path)

        if not filters:
            filters = []

        if type(filters) != type([]):
            raise GbpError("Filters must be a list")

        self._unpack_archive(dir, filters)
        self.unpacked = self._unpacked_toplevel(dir)

    def _unpack_archive(self, dir, filters):
        """
        Unpack packed upstream sources into a given directory.
        """
        ext = os.path.splitext(self.path)[1]
        if ext in [ ".zip", ".xpi" ]:
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
        unpacked.extend(glob.glob("%s/.*" % dir)) # include hidden files and folders
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

    def pack(self, newarchive, filters=[]):
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

        if type(filters) != type([]):
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
        return UpstreamSource(newarchive)

    @staticmethod
    def known_compressions():
        return [ args[1][-1] for args in compressor_opts.items() ]

    def guess_version(self, extra_regex=r''):
        """
        Guess the package name and version from the filename of an upstream
        archive.

        @param extra_regex: extra regular expression to check
        @type extra_regex: raw C{string}

        >>> UpstreamSource('foo-bar_0.2.orig.tar.gz').guess_version()
        ('foo-bar', '0.2')
        >>> UpstreamSource('foo-Bar_0.2.orig.tar.gz').guess_version()
        >>> UpstreamSource('git-bar-0.2.tar.gz').guess_version()
        ('git-bar', '0.2')
        >>> UpstreamSource('git-bar-0.2-rc1.tar.gz').guess_version()
        ('git-bar', '0.2-rc1')
        >>> UpstreamSource('git-bar-0.2:~-rc1.tar.gz').guess_version()
        ('git-bar', '0.2:~-rc1')
        >>> UpstreamSource('git-Bar-0A2d:rc1.tar.bz2').guess_version()
        ('git-Bar', '0A2d:rc1')
        >>> UpstreamSource('git-1.tar.bz2').guess_version()
        ('git', '1')
        >>> UpstreamSource('kvm_87+dfsg.orig.tar.gz').guess_version()
        ('kvm', '87+dfsg')
        >>> UpstreamSource('foo-Bar_0.2.orig.tar.gz').guess_version()
        >>> UpstreamSource('foo-Bar-a.b.tar.gz').guess_version()
        >>> UpstreamSource('foo-bar_0.2.orig.tar.xz').guess_version()
        ('foo-bar', '0.2')
        >>> UpstreamSource('foo-bar_0.2.orig.tar.lzma').guess_version()
        ('foo-bar', '0.2')

        @param extra_regex: additional regex to apply, needs a 'package' and a
                            'version' group
        @return: (package name, version) or None.
        @rtype: tuple
        """
        version_chars = r'[a-zA-Z\d\.\~\-\:\+]'
        if self.is_dir():
            extensions = ''
        else:
            extensions = r'\.tar\.(%s)' % "|".join(self.known_compressions())

        version_filters = map ( lambda x: x % (version_chars, extensions),
                           ( # Debian upstream tarball: package_'<version>.orig.tar.gz'
                             r'^(?P<package>[a-z\d\.\+\-]+)_(?P<version>%s+)\.orig%s',
                             # Upstream 'package-<version>.tar.gz'
                             # or directory 'package-<version>':
                             r'^(?P<package>[a-zA-Z\d\.\+\-]+)-(?P<version>[0-9]%s*)%s'))
        if extra_regex:
            version_filters = extra_regex + version_filters

        for filter in version_filters:
            m = re.match(filter, os.path.basename(self.path))
            if m:
                return (m.group('package'), m.group('version'))
