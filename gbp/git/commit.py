# vim: set fileencoding=utf-8 :
#
# (C) 2011 Guido Günther <agx@sigxcpu.org>
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
"""Git commit class and helpers"""

import re

from gbp.git.modifier import GitModifier


class GitCommit(object):
    """A git commit"""
    sha1_re = re.compile(r'[0-9a-f]{40}$')

    @staticmethod
    def is_sha1(value):
        """
        Is I{value} a valid 40 digit SHA1?

        >>> GitCommit.is_sha1('asdf')
        False
        >>> GitCommit.is_sha1('deadbeef')
        False
        >>> GitCommit.is_sha1('17975594b2d42f2a3d144a9678fdf2c2c1dd96a0')
        True
        >>> GitCommit.is_sha1('17975594b2d42f2a3d144a9678fdf2c2c1dd96a0toolong')
        False

        @param value: the value to check
        @type value: C{str}
        @return: C{True} if I{value} is a 40 digit SHA1, C{False} otherwise.
        @rtype: C{bool}
        """
        return True if GitCommit.sha1_re.match(value) else False


class GitCommitInfo(GitCommit):
    """Metadata for a commit"""

    def __init__(self,
                 commitish: str,
                 commit_sha: str,
                 author: GitModifier,
                 committer: GitModifier,
                 subject: str,
                 patchname: str,
                 body: str,
                 files: dict[str, list[str]]):
        self.commitish = commitish
        self.commit_sha = commit_sha
        self.author = author
        self.committer = committer
        self.subject = subject
        self.patchname = patchname
        self.body = body
        self.files = files

    # GitCommitInfo can be used as a map (for dch format_changelog_entry)
    def get(self, key: str, default=None):
        if key in self.keys() or key == 'id':
            return self.__getitem__(key)
        else:
            return default

    def __getitem__(self, key):
        if key == 'id':
            return self.commitish
        else:
            return self.__dict__[key]

    @staticmethod
    def keys() -> list[str]:
        return ['commitish', 'commit_sha', 'author', 'committer', 'subject'
                'patchname', 'body', 'files']

    def items(self) -> list[tuple]:
        items = []
        for key in self.keys():
            val = self.__getitem__(key)
            if val:
                items.append((key, val))
        return items
