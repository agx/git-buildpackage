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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""provides some debian source package related helpers"""

import os
import re
import subprocess

import gbp.command_wrappers as gbpc
from gbp.errors import GbpError
from gbp.git import GitRepositoryError
from gbp.pkg import UpstreamSource

# Make sure these are available with 'import gbp.deb'
from gbp.deb.changelog import ChangeLog, NoChangeLogError
from gbp.deb.policy import DebianPkgPolicy

# When trying to parse a version-number from a dsc or changes file, these are
# the valid characters.
debian_version_chars = 'a-zA-Z\d.~+-'

class DpkgCompareVersions(gbpc.Command):
    cmd='/usr/bin/dpkg'

    def __init__(self):
        if not os.access(self.cmd, os.X_OK):
            raise GbpError("%s not found - cannot use compare versions" % self.cmd)
        gbpc.Command.__init__(self, self.cmd, ['--compare-versions'])

    def __call__(self, version1, version2):
        self.run_error = "Couldn't compare %s with %s" % (version1, version2)
        res = gbpc.Command.call(self, [ version1, 'lt', version2 ])
        if res not in [ 0, 1 ]:
            raise gbpc.CommandExecFailed("%s: bad return code %d" % (self.run_error, res))
        if res == 0:
            return -1
        elif res == 1:
            res = gbpc.Command.call(self, [ version1, 'gt', version2 ])
            if res not in [ 0, 1 ]:
                raise gbpc.CommandExecFailed("%s: bad return code %d" % (self.run_error, res))
            if res == 0:
                return 1
        return 0


class DscFile(object):
    """Keeps all needed data read from a dscfile"""
    compressions = r"(%s)" % '|'.join(UpstreamSource.known_compressions())
    pkg_re = re.compile(r'Source:\s+(?P<pkg>.+)\s*')
    version_re = re.compile(r'Version:\s((?P<epoch>\d+)\:)?(?P<version>[%s]+)\s*$' % debian_version_chars)
    tar_re = re.compile(r'^\s\w+\s\d+\s+(?P<tar>[^_]+_[^_]+(\.orig)?\.tar\.%s)' % compressions)
    diff_re = re.compile(r'^\s\w+\s\d+\s+(?P<diff>[^_]+_[^_]+\.diff.(gz|bz2))')
    deb_tgz_re = re.compile(r'^\s\w+\s\d+\s+(?P<deb_tgz>[^_]+_[^_]+\.debian.tar.%s)' % compressions)
    format_re = re.compile(r'Format:\s+(?P<format>[0-9.]+)\s*')

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

        f = file(self.dscfile)
        fromdir = os.path.dirname(os.path.abspath(dscfile))
        for line in f:
            m = self.version_re.match(line)
            if m and not self.upstream_version:
                if '-' in m.group('version'):
                    self.debian_version = m.group('version').split("-")[-1]
                    self.upstream_version = "-".join(m.group('version').split("-")[0:-1])
                    self.native = False
                else:
                    self.native = True # Debian native package
                    self.upstream_version = m.group('version')
                if m.group('epoch'):
                    self.epoch = m.group('epoch')
                else:
                    self.epoch = ""
                continue
            m = self.pkg_re.match(line)
            if m:
                self.pkg = m.group('pkg')
                continue
            m = self.deb_tgz_re.match(line)
            if m:
                self.deb_tgz = os.path.join(fromdir, m.group('deb_tgz'))
                continue
            m = self.tar_re.match(line)
            if m:
                self.tgz = os.path.join(fromdir, m.group('tar'))
                continue
            m = self.diff_re.match(line)
            if m:
                self.diff = os.path.join(fromdir, m.group('diff'))
                continue
            m = self.format_re.match(line)
            if m:
                self.pkgformat = m.group('format')
                continue
        f.close()

        if not self.pkg:
            raise GbpError("Cannot parse package name from '%s'" % self.dscfile)
        elif not self.tgz:
            raise GbpError("Cannot parse archive name from '%s'" % self.dscfile)
        if not self.upstream_version:
            raise GbpError("Cannot parse version number from '%s'" % self.dscfile)
        if not self.native and not self.debian_version:
            raise GbpError("Cannot parse Debian version number from '%s'" % self.dscfile)

    def _get_version(self):
        version = [ "", self.epoch + ":" ][len(self.epoch) > 0]
        if self.native:
            version += self.upstream_version
        else:
            version += "%s-%s" % (self.upstream_version, self.debian_version)
        return version

    version = property(_get_version)

    def __str__(self):
        return "<%s object %s>" % (self.__class__.__name__, self.dscfile)


def parse_dsc(dscfile):
    """parse dsc by creating a DscFile object"""
    try:
        dsc = DscFile(dscfile)
    except IOError as err:
        raise GbpError("Error reading dsc file: %s" % err)

    return dsc

def parse_changelog_repo(repo, branch, filename):
    """
    Parse the changelog file from given branch in the git
    repository.
    """
    try:
        # Note that we could just pass in the branch:filename notation
        # to show as well, but we want to check if the branch / filename
        # exists first, so we can give a separate error from other
        # repository errors.
        sha = repo.rev_parse("%s:%s" % (branch, filename))
    except GitRepositoryError:
        raise NoChangeLogError("Changelog %s not found in branch %s" % (filename, branch))

    lines = repo.show(sha)
    return ChangeLog('\n'.join(lines))

def orig_file(cp, compression):
    """
    The name of the orig file belonging to changelog cp

    >>> orig_file({'Source': 'foo', 'Upstream-Version': '1.0'}, "bzip2")
    'foo_1.0.orig.tar.bz2'
    >>> orig_file({'Source': 'bar', 'Upstream-Version': '0.0~git1234'}, "xz")
    'bar_0.0~git1234.orig.tar.xz'
    """
    return DebianPkgPolicy.build_tarball_name(cp['Source'],
                                              cp['Upstream-Version'],
                                              compression)

def get_arch():
    pipe = subprocess.Popen(["dpkg", "--print-architecture"], shell=False, stdout=subprocess.PIPE)
    arch = pipe.stdout.readline().strip()
    return arch


def compare_versions(version1, version2):
    """compares to Debian versionnumbers suitable for sort()"""
    return DpkgCompareVersions()(version1, version2)


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
