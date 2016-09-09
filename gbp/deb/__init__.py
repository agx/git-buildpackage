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
"""provides some debian source package related helpers"""

import os
import subprocess

import gbp.command_wrappers as gbpc
from gbp.errors import GbpError
from gbp.git import GitRepositoryError

# Make sure these are available with 'import gbp.deb'
from gbp.deb.changelog import ChangeLog, NoChangeLogError
from gbp.deb.policy import DebianPkgPolicy


class DpkgCompareVersions(gbpc.Command):
    dpkg = '/usr/bin/dpkg'

    def __init__(self):
        if not os.access(self.dpkg, os.X_OK):
            raise GbpError("%s not found - cannot use compare versions" % self.dpkg)
        gbpc.Command.__init__(self, self.dpkg, ['--compare-versions'], capture_stderr=True)

    def __call__(self, version1, version2):
        """
        Compare two package versions. Return 0 if the versions are equal, -1 1 if version1 < version2,
        and 1 oterwise.

        @raises CommandExecFailed: if the version comparison fails
        """
        self.run_error = "Couldn't compare %s with %s" % (version1, version2)
        res = self.call([version1, 'lt', version2])
        if res not in [0, 1]:
            if self.stderr:
                self.run_error += ' (%s)' % self.stderr
            raise gbpc.CommandExecFailed("%s: bad return code %d" % (self.run_error, res))
        if res == 0:
            return -1
        elif res == 1:
            res = self.call([version1, 'gt', version2])
            if res not in [0, 1]:
                if self.stderr:
                    self.run_error += ' (%s)' % self.stderr
                raise gbpc.CommandExecFailed("%s: bad return code %d" % (self.run_error, res))
            if res == 0:
                return 1
        return 0


def parse_changelog_repo(repo, branch, filename):
    """
    Parse the changelog file from given branch in the git
    repository.

    FIXME: this should use *Vfs methods
    """
    try:
        # Note that we could just pass in the branch:filename notation
        # to show as well, but we want to check if the branch / filename
        # exists first, so we can give a separate error from other
        # repository errors.
        sha = repo.rev_parse("%s:%s" % (branch, filename))
    except GitRepositoryError:
        raise NoChangeLogError("Changelog %s not found in branch %s" % (filename, branch))

    return ChangeLog(repo.show(sha))


def orig_file(cp, compression, component=None):
    """
    The name of the orig file belonging to changelog cp

    >>> orig_file({'Source': 'foo', 'Upstream-Version': '1.0'}, "bzip2")
    'foo_1.0.orig.tar.bz2'
    >>> orig_file({'Source': 'bar', 'Upstream-Version': '0.0~git1234'}, "xz")
    'bar_0.0~git1234.orig.tar.xz'
    >>> orig_file({'Source': 'bar', 'Upstream-Version': '0.0~git1234'}, "xz", component="sub1")
    'bar_0.0~git1234.orig-sub1.tar.xz'
    """
    return DebianPkgPolicy.build_tarball_name(cp['Source'],
                                              cp['Upstream-Version'],
                                              compression,
                                              component=component)


def get_arch():
    pipe = subprocess.Popen(["dpkg", "--print-architecture"], shell=False, stdout=subprocess.PIPE)
    arch = pipe.stdout.readline().strip()
    return arch


def compare_versions(version1, version2):
    """compares to Debian versionnumbers suitable for sort()"""
    return DpkgCompareVersions()(version1, version2)


def get_vendor():
    pipe = subprocess.Popen(["dpkg-vendor", "--query", "Vendor"], shell=False, stdout=subprocess.PIPE)
    return pipe.stdout.readline().strip()


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
