# vim: set fileencoding=utf-8 :
#
# (C) 2011 Guido Guenther <agx@sigxcpu.org>
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
