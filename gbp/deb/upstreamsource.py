# vim: set fileencoding=utf-8 :
#
# (C) 2013 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""Debian-specific upstream sources"""

from gbp.pkg import UpstreamSource
from gbp.deb.policy import DebianPkgPolicy


class DebianUpstreamSource(UpstreamSource):
    """Upstream source class for Debian"""
    def __init__(self, name, unpacked=None):
        super(DebianUpstreamSource, self).__init__(name,
                                                   unpacked,
                                                   DebianPkgPolicy)
