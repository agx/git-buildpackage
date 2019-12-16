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

import re
import os
import gbp.log
from gbp.command_wrappers import Command


class PristineTar(Command):
    """The pristine-tar branch in a git repository"""
    branch = 'pristine-tar'

    def __init__(self, repo):
        self.repo = repo
        super(PristineTar, self).__init__('pristine-tar',
                                          cwd=repo.path,
                                          capture_stderr=True)

    def _has_in_output(self, match):
        """
        Check if pristine_tar has a certain feature enabled.

        @param feature: feature / command option to check
        @type feature: C{str}
        @return: True if feature is supported
        @rtype: C{bool}
        """
        self.call(['--help'], quiet=True)  # There's no --help so we always exit 1
        r = re.compile(match)
        for line in self.stderr.splitlines():
            if r.match(line):
                return True
        return False

    def has_feature_verify(self):
        """Does this pristine-tar support tarball verification"""
        return self._has_in_output(".* pristine-tar .* verify")

    def has_feature_sig(self):
        """Does this pristine-tar support detached upstream signatures"""
        return self._has_in_output(r'.*--signature-file')

    def has_commit(self, archive_regexp):
        """
        Do we have a pristine-tar commit for a package matching I{archive_regexp}.

        @param archive_regexp: archive name to look for (regexp wildcards allowed)
        @type archive_regexp: C{str}
        """
        return True if self.get_commit(archive_regexp)[0] else False

    def _commit_contains_file(self, commit, regexp):
        """Does the given commit contain a file with the given regex"""
        files = self.repo.get_commit_info(commit)['files']
        cregex = re.compile(regexp)
        for _, v in files.items():
            for f in v:
                if cregex.match(f.decode()):
                    return True
        return False

    def get_commit(self, archive_regexp):
        """
        Get the pristine-tar commit of a package matching I{archive_regexp}.
        Checks also whether the commit contains a signature file.

        @param archive_regexp: archive name to look for (regexp wildcards allowed)
        @type archive_regexp: C{str}
        @return: Commit, True if commit contains a signature file
        @rtype: C{tuple} of C{str} and C{bool}
        """
        if not self.repo.has_pristine_tar_branch():
            return None, False

        regex = ('pristine-tar .* %s' % archive_regexp)
        commits = self.repo.grep_log(regex, self.branch, merges=False)
        if commits:
            commit = commits[-1]
            gbp.log.debug("Found pristine-tar commit at '%s'" % commit)
            return commit, self._commit_contains_file(commit, '%s.asc' % archive_regexp)
        return None, False

    def checkout(self, archive, quiet=False, signaturefile=None):
        """
        Checkout an orig archive from pristine-tar branch

        @param archive: the name of the orig archive
        @type archive: C{str}
        """
        args = ['checkout', archive]
        self.run_error = 'Pristine-tar couldn\'t checkout "%s": {stderr_or_reason}' % os.path.basename(archive)
        if signaturefile and self.has_feature_sig():
            args += ['-s', signaturefile]
        self.__call__(args, quiet=quiet)

    def commit(self, archive, upstream, quiet=False, signaturefile=None):
        """
        Commit an archive I{archive} to the pristine tar branch using upstream
        branch ${upstream}.

        @param archive: the archive to commit
        @type archive: C{str}
        @param upstream: the upstream branch to diff against
        @type upstream: C{str}
        """
        args = ['commit', archive, upstream]
        self.run_error = ("Couldn't commit to '%s' with upstream '%s': {stderr_or_reason}" %
                          (self.branch, upstream))
        if signaturefile and self.has_feature_sig():
            args += ['-s', signaturefile]
        self.__call__(args, quiet=quiet)

    def verify(self, archive, quiet=False):
        """Verify an archive's I{archive} checksum using to the pristine tar branch"""

        self.run_error = 'Pristine-tar couldn\'t verify "%s": {stderr_or_reason}' % os.path.basename(archive)
        self.__call__(['verify', archive], quiet=quiet)
