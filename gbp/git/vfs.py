# vim: set fileencoding=utf-8 :
#
# (C) 2013 Guido Günther <agx@sigxcpu.org>
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
"""Make blobs in a git repository accessible as file like objects"""

import io
from gbp.git.repository import GitRepositoryError


class GitVfs(object):

    class _File(object):
        """
        A file like object representing a file in git

        @todo: We don't support any byte ranges yet.
        """
        def __init__(self, content, binary=False):
            self._iter = iter
            if binary:
                self._data = io.BytesIO(content)
            else:
                self._data = io.StringIO(content.decode())

        def readline(self):
            return self._data.readline()

        def readlines(self):
            return self._data.readlines()

        def read(self, size=None):
            return self._data.read(size)

        def close(self):
            return self._data.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()

    def __init__(self, repo, committish=None):
        """
        @param repo: the git repository to act on
        @param committish: the committish to act on
        """
        self._repo = repo
        self._committish = committish or 'HEAD'

    def open(self, path, flags=None):
        flags = flags or 'r'

        for flag in flags:
            if flag not in ['r', 't', 'b']:
                raise NotImplementedError("Flag '%s' unsupported so far" % flag)
        try:
            return GitVfs._File(self._repo.show(
                "%s:%s" % (self._committish, path)),
                True if 'b' in flags else False)
        except GitRepositoryError as e:
            raise OSError(e)
