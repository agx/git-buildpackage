# vim: set fileencoding=utf-8 :
#
# (C) 2012 Guido Günther <agx@sigxcpu.org>
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
"""Handle checkin and checkout of archives from the pristine-tar branch"""

from gbp.pkg import compressor_opts
from gbp.pkg.pristinetar import PristineTar
from gbp.deb import DebianPkgPolicy


class DebianPristineTar(PristineTar):
    """The pristine-tar branch in a Debian git repository"""
    def has_commit(self, package, version, comp_type=None):
        """
        Do we have a pristine-tar commit for package I{package} at version
        {version} with compression type I{comp_type}?

        @param package: the package to look for
        @type package: C{str}
        @param version: the upstream version to look for
        @type version: C{str}
        @param comp_type: the compression type
        @type comp_type: C{str}
        """
        if not comp_type:
            ext = '\w\+'
        else:
            ext = compressor_opts[comp_type][1]

        name_regexp = '%s_%s\.orig\.tar\.%s' % (package, version, ext)

        return super(DebianPristineTar, self).has_commit(name_regexp)

    def checkout(self, package, version, comp_type, output_dir, component=None):
        """
        Checkout the orig tarball for package I{package} of I{version} and
        compression type I{comp_type} to I{output_dir}

        @param package: the package to generate the orig tarball for
        @type package: C{str}
        @param version: the version to check generate the orig tarball for
        @type version: C{str}
        @param comp_type: the compression type of the tarball
        @type comp_type: C{str}
        @param output_dir: the directory to put the tarball into
        @type output_dir: C{str}
        """
        name = DebianPkgPolicy.build_tarball_name(package,
                                                  version,
                                                  comp_type,
                                                  output_dir,
                                                  component=component)
        super(DebianPristineTar, self).checkout(name)
