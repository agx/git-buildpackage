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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Handle checkin and checkout of archives from the pristine-tar branch"""

import os, re
from gbp.command_wrappers import Command
from gbp.deb import UpstreamSource, compressor_opts

class PristineTar(Command):
    """The pristine-tar branch in a git repository"""
    cmd='/usr/bin/pristine-tar'
    branch = 'pristine-tar'

    def __init__(self, repo):
        self.repo = repo
        super(PristineTar, self).__init__(self.cmd, cwd=repo.path)

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
        return True if self.get_commit(package, version, comp_type) else False

    def get_commit(self, package, version, comp_type=None):
        """
        Get the pristine-tar commit of package I{package} in version I{version}
        and compression type I{comp_type}

        @param package: the package to look for
        @type package: C{str}
        @param version: the version to look for
        @param comp_type: the compression type
        @type comp_type: C{str}
        """
        if not self.repo.has_pristine_tar_branch():
            return None

        if not comp_type:
            ext = '\w+'
        else:
            ext = compressor_opts[comp_type][1]

        regex = ('pristine-tar .* %s_%s\.orig\.tar\.%s' %
                 (package, version, ext))
        commits = self.repo.grep_log(regex, self.branch)
        if commits:
            commit = commits[-1]
            gbp.log.debug("Found pristine-tar commit at '%s'" % commit)
            return commit
        return None

    def _checkout(self, archive):
        self.run_error = 'Couldn\'t checkout "%s"' % os.path.basename(archive)
        self.__call__(['checkout', archive])

    def checkout(self, package, version, comp_type, output_dir):
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
        name = UpstreamSource.build_tarball_name(package,
                                                 version,
                                                 comp_type,
                                                 output_dir)
        self._checkout(name)

    def commit(self, archive, upstream):
        """
        Commit an archive I{archive} to the pristine tar branch using upstream
        branch ${upstream}.

        @param archive: the archive to commit
        @type archive: C{str}
        @param upstream: the upstream branch to diff against
        @type upstream: C{str}
        """
        ref = 'refs/heads/%s' % upstream

        self.run_error = ("Couldn't commit to '%s' with upstream '%s'" %
                          (self.branch, upstream))
        self.__call__(['commit', archive, upstream])

