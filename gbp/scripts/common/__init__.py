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
import traceback
from gbp.errors import GbpError
from gbp.deb import DebianPkgPolicy
from gbp.pkg import Archive
from gbp.deb.upstreamsource import DebianAdditionalTarball


class ExitCodes(object):
    ok = 0,
    failed = 1               # All other errors
    no_value = 2             # Value does not exist (gbp config only)
    parse_error = 3          # Failed to parse configuration file
    uscan_up_to_date = 4     # Uscan up to date (import-orig only)


def maybe_debug_raise():
    if 'raise' in os.getenv("GBP_DEBUG", '').split(','):
        raise


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


# FIXME: this could become a method of DebianUpstreamSource
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
        sig = cname + '.asc'
        if not os.path.exists(sig):
            sig = None
        tarballs.append(DebianAdditionalTarball(cname, component, sig=sig))
        if not os.path.exists(cname):
            raise GbpError("Cannot find component tarball %s" % cname)
    return tarballs


def debug_exc(options):
    if options.verbose:
        traceback.print_exc()
