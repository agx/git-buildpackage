# vim: set fileencoding=utf-8 :
#
# (C) 2021 Andrej Shadura <andrewsh@debian.org>
# (C) 2021 Collabora Ltd
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
"""Check in and check out archives from the pristine-lfs branch"""

from __future__ import annotations

import logging

from gbp.command_wrappers import CommandExecFailed
from gbp.git import GitRepository, GitRepositoryError

try:
    from pristine_lfs.main import do_list, do_verify, do_commit_files, do_checkout
    from pristine_lfs.errors import CommandFailed, DifferentFilesExist, GitError
except ImportError:
    def pristine_lfs_not_found(*args, **kwargs):
        raise CommandExecFailed("pristine-lfs not installed")

    do_list = do_verify = do_checkout = do_commit_files = pristine_lfs_not_found

    class DifferentFilesExist(Exception):
        pass

    GitError = DifferentFilesExist

logger = logging.getLogger('pristine-lfs')


class PristineLfs:
    branch = 'pristine-lfs'

    def __init__(self, repo: GitRepository):
        self.repo = repo

    def commit(self, files: list[str], quiet: bool = False):
        """
        Commit files I{files} to the pristine-lfs branch

        @param files: list of files to commit
        @type files: C{list}
        """
        logger.setLevel(logging.WARNING if quiet else logging.INFO)

        try:
            ios = [open(f, 'rb') for f in files]
            do_commit_files(tarballs=ios, branch=self.branch)
        except (OSError, CommandFailed) as e:
            raise CommandExecFailed(str(e))
        except (DifferentFilesExist, GitError) as e:
            raise GitRepositoryError(str(e))

    def checkout(self, package: str, version: str, output_dir: str, quiet: bool = False):
        """
        Check out all orig tarballs for package I{package} of I{version} to
        I{output_dir}

        @param package: the package to check out the orig tarballs for
        @type package: C{str}
        @param version: the version to check out the orig tarballs for
        @type version: C{str}
        @param output_dir: the directory to put the tarballs into
        @type output_dir: C{str}
        """
        logger.setLevel(logging.WARNING if quiet else logging.INFO)

        try:
            do_checkout(package=package, version=version, branch=self.branch, outdir=output_dir)
        except (OSError, CommandFailed) as e:
            raise CommandExecFailed(str(e))
        except GitError as e:
            raise GitRepositoryError(str(e))
