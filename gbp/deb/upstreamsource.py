# vim: set fileencoding=utf-8 :
#
# (C) 2013 Intel Corporation <markus.lehtonen@linux.intel.com>
# (C) 2016 Guido Günther <agx@sigxcpu.org>
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
"""Debian-specific upstream sources"""

from gbp.pkg import UpstreamSource
from gbp.deb.policy import DebianPkgPolicy
import gbp.command_wrappers

import os
import shutil
import tempfile


class DebianUpstreamSource(UpstreamSource):
    """Upstream source class for Debian"""
    def __init__(self, name, unpacked=None, sig=None):
        super(DebianUpstreamSource, self).__init__(name,
                                                   unpacked=unpacked,
                                                   sig=sig,
                                                   pkg_policy=DebianPkgPolicy)


class DebianAdditionalTarball(DebianUpstreamSource):
    """Upstream source class for additional tarballs"""
    def __init__(self, name, component, unpacked=None, sig=None):
        self.component = component
        super(DebianAdditionalTarball, self).__init__(name,
                                                      unpacked=unpacked,
                                                      sig=sig)

    def unpack(self, dest, filters):
        """
        Unpack the additional tarball into {dir} naming it
        I{component}.  Apply filters during unpack.

        @param dir: the main tarball dir
        @param filters: filters to apply

        We can't simply use unpack since we need to remove any preexisting dirs and
        name the target directory after the component name.
        """
        olddir = os.path.abspath(os.path.curdir)
        tmpdir = None
        try:
            tmpdir = os.path.abspath(tempfile.mkdtemp(dir=os.path.join(dest, '..')))
            super(DebianAdditionalTarball, self).unpack(tmpdir, filters)

            newdest = os.path.join(dest, self.component)
            if os.path.exists(newdest):
                shutil.rmtree(newdest)
            shutil.move(self.unpacked, newdest)
        finally:
            os.chdir(olddir)
            if tmpdir is not None:
                gbp.command_wrappers.RemoveTree(tmpdir)()


type DebianUpstreamTarballList = list[DebianUpstreamSource | DebianAdditionalTarball]
