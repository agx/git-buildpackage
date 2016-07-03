# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007,2011 Guido Günther <agx@sigxcpu.org>
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
"""
Debian Packaging policies

like allowed characters in version numbers, etc.
"""

import os
import re

from gbp.pkg import (PkgPolicy, compressor_opts)


class DebianPkgPolicy(PkgPolicy):
    """
    Packaging policy for Debian Source Packages

    >>> DebianPkgPolicy.is_valid_upstreamversion('1:9.8.4.dfsg.P1-6')
    True
    >>> DebianPkgPolicy.is_valid_upstreamversion('-1')
    False
    """

    # Valid package names according to Debian Policy Manual 5.6.1:
    # "Package names (both source and binary, see Package, Section 5.6.7)
    # must consist only of lower case letters (a-z), digits (0-9), plus (+)
    # and minus (-) signs, and periods (.). They must be at least two
    # characters long and must start with an alphanumeric character."
    packagename_re = re.compile("^[a-zA-Z0-9][a-zA-Z0-9\.\+\-~]+$")
    packagename_msg = """Package names must be at least two characters long, start with an
    alphanumeric and can only containg letters (a-z,A-Z), digits
    (0-9), plus signs (+), minus signs (-), periods (.) and hyphens (~)"""

    # Valid upstream versions according to Debian Policy Manual 5.6.12:
    # "The upstream_version may contain only alphanumerics[32] and the
    # characters . + - : ~ (full stop, plus, hyphen, colon, tilde) and
    # should start with a digit. If there is no debian_revision then hyphens
    # are not allowed; if there is no epoch then colons are not allowed."
    # Since we don't know about any epochs and debian revisions yet, the
    # last two conditions are not checked.
    upstreamversion_re = re.compile("^[0-9][a-zA-Z0-9\.\+\-\:\~]*$")
    upstreamversion_msg = """Upstream version numbers must start with a digit and can only containg lower case
    letters (a-z), digits (0-9), full stops (.), plus signs (+), minus signs
    (-), colons (:) and tildes (~)"""

    # Valid characters in a debian version
    debianversion_chars = 'a-zA-Z\\d.~+-'

    @staticmethod
    def build_tarball_name(name, version, compression, dir=None, component=None):
        """
        Given a source package's I{name}, I{version} and I{compression}
        return the name of the corresponding upstream tarball.

        >>> DebianPkgPolicy.build_tarball_name('foo', '1.0', 'bzip2')
        'foo_1.0.orig.tar.bz2'
        >>> DebianPkgPolicy.build_tarball_name('bar', '0.0~git1234', 'xz')
        'bar_0.0~git1234.orig.tar.xz'
        >>> DebianPkgPolicy.build_tarball_name('bar', '0.0~git1234', 'xz', component="foo")
        'bar_0.0~git1234.orig-foo.tar.xz'

        @param name: the source package's name
        @type name: C{str}
        @param version: the upstream version
        @type version: C{str}
        @param compression: the desired compression
        @type compression: C{str}
        @param dir: a directory to prepend
        @type dir: C{str}
        @return: the tarballs name corresponding to the input parameters
        @rtype: C{str}
        """
        ext = compressor_opts[compression][1]
        sub = '-{0}'.format(component) if component else ''
        tarball = "%s_%s.orig%s.tar.%s" % (name, version, sub, ext)
        if dir:
            tarball = os.path.join(dir, tarball)
        return tarball
