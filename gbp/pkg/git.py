# vim: set fileencoding=utf-8 :
#
# (C) 2017 Guido Günther <agx@sigxcpu.org>
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
"""A Git Repository that keeps a Distro Package"""

import os
import shutil
import tempfile

from gbp.command_wrappers import (CatenateTarArchive, CatenateZipArchive)
from gbp.git import GitRepository, GitRepositoryError
from gbp.deb.pristinetar import DebianPristineTar
from gbp import pipes

import gbp.log


class PkgGitRepository(GitRepository):
    """A git repository that holds the source of a Distro package"""

    def __init__(self, *args, **kwargs):
        super(PkgGitRepository, self).__init__(*args, **kwargs)
        self.pristine_tar = DebianPristineTar(self)

    @staticmethod
    def sanitize_prefix(prefix):
        """
        Make sure git-archive prefix ends with a slash

        >>> PkgGitRepository.sanitize_prefix('')
        '/'
        >>> PkgGitRepository.sanitize_prefix('foo/')
        'foo/'
        >>> PkgGitRepository.sanitize_prefix('/foo/bar')
        'foo/bar/'
        """
        if prefix:
            return prefix.strip('/') + '/'
        return '/'

    def archive_comp(self, treeish, output, prefix, comp, format='tar', submodules=False):
        """Create a compressed source tree archive with the given options"""
        if comp and not comp.is_known():
            raise GitRepositoryError("Unsupported compression type '%s'" % comp.type)

        if submodules:
            return self._archive_comp_submodules(treeish, output, prefix, comp, format)
        else:
            return self._archive_comp_single(treeish, output, prefix, comp, format)

    def _archive_comp_submodules(self, treeish, output, prefix, comp, format='tar'):
        """
        Create a compressed source tree archive with submodules.

        Concatenates the archives generated by git-archive into one and compresses
        the end result.

        Exception handling is left to the caller.
        """
        prefix = self.sanitize_prefix(prefix)
        tempdir = tempfile.mkdtemp()
        main_archive = os.path.join(tempdir, "main.%s" % format)
        submodule_archive = os.path.join(tempdir, "submodule.%s" % format)
        try:
            # generate main (tmp) archive
            self.archive(format=format, prefix=prefix,
                         output=main_archive, treeish=treeish)

            # generate each submodule's archive and append it to the main archive
            for (subdir, commit) in self.get_submodules(treeish):
                tarpath = [subdir, subdir[2:]][subdir.startswith("./")]

                gbp.log.debug("Processing submodule %s (%s)" % (subdir, commit[0:8]))
                self.archive(format=format, prefix='%s%s/' % (prefix, tarpath),
                             output=submodule_archive, treeish=commit, cwd=subdir)
                if format == 'tar':
                    CatenateTarArchive(main_archive)(submodule_archive)
                elif format == 'zip':
                    CatenateZipArchive(main_archive)(submodule_archive)

            # compress the output
            if comp and comp.type:
                # Redirect through stdout directly to the correct output file in
                # order to avoid determining the output filename of the compressor
                ret = os.system("%s %s > %s" % (comp.cmdline(), main_archive, output))
                if ret:
                    raise GitRepositoryError("Error creating %s: %d" % (output, ret))
            else:
                shutil.move(main_archive, output)
        finally:
            shutil.rmtree(tempdir)

    def _archive_comp_single(self, treeish, output, prefix, comp, format='tar'):
        """
        Create a compressed source tree archive without submodules

        We have this as a special case since it avoids a temporary file
        """
        prefix = self.sanitize_prefix(prefix)
        pipe = pipes.Template()
        pipe.prepend("git archive --format=%s --prefix=%s %s" % (format, prefix, treeish), '.-')
        if comp and comp.type:
            pipe.append(comp.cmdline(), '--')
        ret = pipe.copy('', output)
        if ret:
            raise GitRepositoryError("Error creating %s: %d" % (output, ret))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
