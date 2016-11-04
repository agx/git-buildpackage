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

import os
import gbp.log
from gbp.command_wrappers import Command


class PristineTar(Command):
    """The pristine-tar branch in a git repository"""
    cmd = '/usr/bin/pristine-tar'
    branch = 'pristine-tar'

    def __init__(self, repo):
        self.repo = repo
        super(PristineTar, self).__init__(self.cmd, cwd=repo.path, capture_stderr=True)

    def has_commit(self, archive_regexp):
        """
        Do we have a pristine-tar commit for a package matching I{archive_regexp}.

        @param archive_regexp: archive name to look for (regexp wildcards allowed)
        @type archive_regexp: C{str}
        """
        return True if self.get_commit(archive_regexp) else False

    def get_commit(self, archive_regexp):
        """
        Get the pristine-tar commit of a package matching I{archive_regexp}.

        @param archive_regexp: archive name to look for (regexp wildcards allowed)
        @type archive_regexp: C{str}
        """
        if not self.repo.has_pristine_tar_branch():
            return None

        regex = ('pristine-tar .* %s' % archive_regexp)
        commits = self.repo.grep_log(regex, self.branch)
        if commits:
            commit = commits[-1]
            gbp.log.debug("Found pristine-tar commit at '%s'" % commit)
            return commit
        return None

    def checkout(self, archive):
        """
        Checkout an orig archive from pristine-tar branch

        @param archive: the name of the orig archive
        @type archive: C{str}
        """
        self.run_error = 'Pristine-tar couldn\'t checkout "%s": {stderr_or_reason}' % os.path.basename(archive)
        self.__call__(['checkout', archive])

    def commit(self, archive, upstream):
        """
        Commit an archive I{archive} to the pristine tar branch using upstream
        branch ${upstream}.

        @param archive: the archive to commit
        @type archive: C{str}
        @param upstream: the upstream branch to diff against
        @type upstream: C{str}
        """
        self.run_error = ("Couldn't commit to '%s' with upstream '%s': {stderr_or_reason}" %
                          (self.branch, upstream))
        self.__call__(['commit', archive, upstream])
