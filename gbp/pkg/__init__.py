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

import gbp.log
import gbp.command_wrappers as gbpc
from gbp.errors import GbpError
from gbp.command_wrappers import Command

# compression types, extra options and extensions
compressor_opts = { 'gzip'  : [ '-n', 'gz' ],
                    'bzip2' : [ '', 'bz2' ],
                    'lzma'  : [ '', 'lzma' ],
                    'xz'    : [ '', 'xz' ] }

# Map frequently used names of compression types to the internal ones:
compressor_aliases = { 'bz2' : 'bzip2',
                       'gz'  : 'gzip', }

class PkgPolicy(object):
    @classmethod
    def is_valid_packagename(cls, name):
        "Is this a valid package name?"
        return cls.packagename_re.match(name)

    @classmethod
    def is_valid_upstreamversion(cls, version):
        "Is this a valid upstream version number?"
        return cls.upstreamversion_re.match(version)

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

