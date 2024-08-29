# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007,2011,2013 Guido Günther <agx@sigxcpu.org>
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
"""provides some debian source package related helpers"""

import os
import re

from gbp.errors import GbpError
from gbp.deb.upstreamsource import DebianUpstreamSource
from gbp.deb.policy import DebianPkgPolicy


class DscFile(object):
    """Keeps data read from a dscfile"""
    compressions = r"(%s)" % '|'.join(DebianUpstreamSource.known_compressions())
    pkg_re = re.compile(r'Source:\s+(?P<pkg>.+)\s*')
    version_re = re.compile(r'Version:\s((?P<epoch>\d+)\:)?'
                            r'(?P<version>[%s]+)\s*$'
                            % DebianPkgPolicy.debianversion_chars)
    tar_re = re.compile(r'^\s\w+\s\d+\s+(?P<tar>[^_]+_[^_]+'
                        r'(\.orig)?\.tar\.%s)$' % compressions)
    add_tar_re = re.compile(r'^\s\w+\s\d+\s+(?P<tar>[^_]+_[^_]+'
                            r'\.orig-(?P<dir>[a-zA-Z0-9-]+)\.tar\.%s)$' % compressions)
    diff_re = re.compile(r'^\s\w+\s\d+\s+(?P<diff>[^_]+_[^_]+'
                         r'\.diff.(gz|bz2))$')
    deb_tgz_re = re.compile(r'^\s\w+\s\d+\s+(?P<deb_tgz>[^_]+_[^_]+'
                            r'\.debian.tar.%s)$' % compressions)
    format_re = re.compile(r'Format:\s+(?P<format>[0-9.]+)\s*(?:\((?P<subtype>native|quilt|git)\))?')
    sig_re = re.compile(r'^\s\w+\s\d+\s+(?P<sig>[^_]+_[^_]+'
                        r'\.orig(-[a-z0-9-]+)?\.tar\.%s.asc)$' % compressions)

    def __init__(self, dscfile):
        self.pkg = ""
        self.tgz = ""
        self.diff = ""
        self.deb_tgz = ""
        self.pkgformat = "1.0"
        self.debian_version = ""
        self.upstream_version = ""
        self.native = False
        self.dscfile = os.path.abspath(dscfile)

        try:
            with open(self.dscfile, encoding='utf-8') as f:
                self._parse_file(f)
        except UnicodeDecodeError:
            raise GbpError(f"{self.dscfile} is not UTF-8 encoded")

        if self.pkgformat == "1.0":
            self.native = self.diff == ""
        else:
            self.native = self.subtype == 'native'
        if self.native:
            # Source format 1.0 native versions may contain hyphens.  Examples:
            # http://snapshot.debian.org/package/python3-defaults/3.10.6-1/
            # http://archive.ubuntu.com/ubuntu/pool/main/p/pam/pam_1.1.8-3.6ubuntu2.18.04.6.dsc
            self.upstream_version = self.full_version
        else:
            self.upstream_version, separator, self.debian_version = self.full_version.rpartition('-')
            if separator:
                if not self.debian_version:
                    raise GbpError("Cannot parse Debian version number from '%s'" % self.dscfile)
                if not self.upstream_version:
                    raise GbpError("Cannot parse upstream version number from '%s'" % self.dscfile)
            else:
                # Source format 1.0 non-native versions without hyphen:
                # http://snapshot.debian.org/package/latencytop/0.5/
                self.upstream_version = self.full_version
                self.debian_version = ''

        if not self.pkg:
            raise GbpError("Cannot parse package name from '%s'" % self.dscfile)
        elif not self.tgz:
            raise GbpError("Cannot parse archive name from '%s'" % self.dscfile)
        if not self.upstream_version:
            raise GbpError("Cannot parse version number from '%s'" % self.dscfile)

    def _parse_file(self, f):
        sigs = []
        add_tars = []
        fromdir = os.path.dirname(self.dscfile)

        for line in f:
            m = self.version_re.match(line)
            if m:
                self.full_version = m.group('version')
                self.epoch = m.group('epoch') or ''
                continue
            m = self.pkg_re.match(line)
            if m:
                self.pkg = m.group('pkg')
                continue
            m = self.deb_tgz_re.match(line)
            if m:
                self.deb_tgz = os.path.join(fromdir, m.group('deb_tgz'))
                continue
            m = self.add_tar_re.match(line)
            if m:
                add_tars.append((m.group('dir'),
                                 os.path.join(fromdir, m.group('tar'))))
                continue
            m = self.tar_re.match(line)
            if m:
                self.tgz = os.path.join(fromdir, m.group('tar'))
                continue
            m = self.sig_re.match(line)
            if m:
                sigs.append(os.path.join(fromdir, m.group('sig')))
                continue
            m = self.diff_re.match(line)
            if m:
                self.diff = os.path.join(fromdir, m.group('diff'))
                continue
            m = self.format_re.match(line)
            if m:
                self.pkgformat = m.group('format')
                self.subtype = m.group('subtype') or ''
                continue

        self.additional_tarballs = dict(add_tars)
        self.sigs = list(set(sigs))

    @property
    def version(self):
        version = ["", self.epoch + ":"][len(self.epoch) > 0]
        if self.native:
            version += self.upstream_version
        else:
            if self.debian_version != '':
                version += "%s-%s" % (self.upstream_version, self.debian_version)
            else:   # possible in 1.0
                version += "%s" % self.upstream_version
        return version

    def __str__(self):
        return "<%s object %s>" % (self.__class__.__name__, self.dscfile)

    @classmethod
    def parse(cls, filename):
        try:
            dsc = cls(filename)
        except IOError as err:
            raise GbpError("Error reading dsc file: %s" % err)
        return dsc

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
