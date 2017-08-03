# vim: set fileencoding=utf-8 :
#
# (C) 2017 Guido Guenther <agx@sigxcpu.org>
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


import os
import re

from gbp.pkg.archive import Archive


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
    def guess_upstream_src_version(filename, extra_regex=r''):
        """
        Guess the package name and version from the filename of an upstream
        archive.

        @param filename: filename (archive or directory) from which to guess
        @type filename: C{string}
        @param extra_regex: additional regex to apply, needs a 'package' and a
                            'version' group
        @return: (package name, version) or ('', '')
        @rtype: tuple

        >>> PkgPolicy.guess_upstream_src_version('foo-bar_0.2.orig.tar.gz')
        ('foo-bar', '0.2')
        >>> PkgPolicy.guess_upstream_src_version('foo-Bar_0.2.orig.tar.gz')
        ('', '')
        >>> PkgPolicy.guess_upstream_src_version('git-bar-0.2.tar.gz')
        ('git-bar', '0.2')
        >>> PkgPolicy.guess_upstream_src_version('git-bar-0.2-rc1.tar.gz')
        ('git-bar', '0.2-rc1')
        >>> PkgPolicy.guess_upstream_src_version('git-bar-0.2:~-rc1.tar.gz')
        ('git-bar', '0.2:~-rc1')
        >>> PkgPolicy.guess_upstream_src_version('git-Bar-0A2d:rc1.tar.bz2')
        ('git-Bar', '0A2d:rc1')
        >>> PkgPolicy.guess_upstream_src_version('git-1.tar.bz2')
        ('git', '1')
        >>> PkgPolicy.guess_upstream_src_version('kvm_87+dfsg.orig.tar.gz')
        ('kvm', '87+dfsg')
        >>> PkgPolicy.guess_upstream_src_version('foo-Bar-a.b.tar.gz')
        ('', '')
        >>> PkgPolicy.guess_upstream_src_version('foo-bar_0.2.orig.tar.xz')
        ('foo-bar', '0.2')
        >>> PkgPolicy.guess_upstream_src_version('foo-bar_0.2.orig.tar.lzma')
        ('foo-bar', '0.2')
        >>> PkgPolicy.guess_upstream_src_version('foo-bar-0.2.zip')
        ('foo-bar', '0.2')
        >>> PkgPolicy.guess_upstream_src_version('foo-bar-0.2.tlz')
        ('foo-bar', '0.2')
        >>> PkgPolicy.guess_upstream_src_version('foo-bar_0.2.tar.gz')
        ('foo-bar', '0.2')
        """
        version_chars = r'[a-zA-Z\d\.\~\-\:\+]'
        basename = Archive.parse_filename(os.path.basename(filename))[0]

        version_filters = map(
            lambda x: x % version_chars,
            (  # Debian upstream tarball: package_'<version>.orig.tar.gz'
                r'^(?P<package>[a-z\d\.\+\-]+)_(?P<version>%s+)\.orig',
                # Debian native: 'package_<version>.tar.gz'
                r'^(?P<package>[a-z\d\.\+\-]+)_(?P<version>%s+)',
                # Upstream 'package-<version>.tar.gz'
                # or directory 'package-<version>':
                r'^(?P<package>[a-zA-Z\d\.\+\-]+)(-)(?P<version>[0-9]%s*)'))
        if extra_regex:
            version_filters = extra_regex + version_filters

        for filter in version_filters:
            m = re.match(filter, basename)
            if m:
                return (m.group('package'), m.group('version'))
        return ('', '')

    @staticmethod
    def has_origs(orig_files, dir):
        "Check orig tarball and additional tarballs exists in dir"
        for o in orig_files:
            if not os.path.exists(os.path.join(dir, o)):
                return False
        return True

    @classmethod
    def has_orig(cls, orig_file, dir):
        return cls.has_origs([orig_file], dir)

    @staticmethod
    def symlink_origs(orig_files, orig_dir, output_dir, force=False):
        """
        symlink orig tarball from orig_dir to output_dir
        @return: [] if all links were created, list of
                 failed links otherwise
        """
        orig_dir = os.path.abspath(orig_dir)
        output_dir = os.path.abspath(output_dir)
        err = []

        if orig_dir == output_dir:
            return []

        for f in orig_files:
            src = os.path.join(orig_dir, f)
            dst = os.path.join(output_dir, f)
            if not os.access(src, os.F_OK):
                err.append(f)
                continue
            try:
                if os.path.exists(dst) and force:
                    os.unlink(dst)
                os.symlink(src, dst)
            except OSError:
                err.append(f)
        return err

    @classmethod
    def symlink_orig(cls, orig_file, orig_dir, output_dir, force=False):
        return cls.symlink_origs([orig_file], orig_dir, output_dir, force=force)
