# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007,2008,2011 Guido Guenther <agx@sigxcpu.org>
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
"""Accessing Git from python"""

import calendar
import dateutil.parser

from gbp.git.modifier import GitModifier   # noqa: F401
from gbp.git.commit import GitCommit       # noqa: F401
from gbp.git.errors import GitError        # noqa: F401
from gbp.git.repository import (           # noqa: F401
    GitRepository, GitRepositoryError)
from gbp.git.fastimport import FastImport  # noqa: F401
from gbp.git.args import GitArgs           # noqa: F401
from gbp.git.vfs import GitVfs             # noqa: F401


def rfc822_date_to_git(rfc822_date):
    """Parse a date in RFC822 format, and convert to a 'seconds tz' C{str}ing.

    >>> rfc822_date_to_git('Thu, 1 Jan 1970 00:00:01 +0000')
    '1 +0000'
    >>> rfc822_date_to_git('Thu, 20 Mar 2008 01:12:57 -0700')
    '1206000777 -0700'
    >>> rfc822_date_to_git('Sat, 5 Apr 2008 17:01:32 +0200')
    '1207407692 +0200'
    """
    d = dateutil.parser.parse(rfc822_date)
    seconds = calendar.timegm(d.utctimetuple())
    tz = d.strftime("%z")
    return '%d %s' % (seconds, tz)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
