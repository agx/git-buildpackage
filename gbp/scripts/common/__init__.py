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
"""Parts shared between the deb and rpm commands"""

import re
import os
from gbp.errors import GbpError
from gbp.deb import DebianPkgPolicy
from gbp.pkg import Archive


class ExitCodes(object):
    ok = 0,
    failed = 1               # All other errors
    no_value = 2             # Value does not exist (gbp config only)
    parse_error = 3          # Failed to parse configuration file


def is_download(args):
    """
    >>> is_download(["http://foo.example.com"])
    True
    >>> is_download([])
    False
    >>> is_download(["foo-1.1.orig.tar.gz"])
    False
    """
    if args and re.match("https?://", args[0]):
        return True
    return False


def get_component_tarballs(name, version, tarball, components):
    """
    Figure out the paths to the component tarballs based on the main
    tarball.
    """
    tarballs = []
    (_, _, comp_type) = Archive.parse_filename(tarball)
    for component in components:
        cname = DebianPkgPolicy.build_tarball_name(name,
                                                   version,
                                                   comp_type,
                                                   os.path.dirname(tarball),
                                                   component)
        tarballs.append((component, cname))
        if not os.path.exists(cname):
            raise GbpError("Can not find component tarball %s" % cname)
    return tarballs
