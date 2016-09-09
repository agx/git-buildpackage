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
"""
Someone who modifiers something in git

like committing changes or authoring a patch
"""

import six
import calendar
import datetime

from gbp.git.errors import GitError


class GitModifierError(GitError):
    """Exception thrown by L{GitModifier}"""
    pass


class GitTz(datetime.tzinfo):
    """Simple class to store the utc offset only"""
    def __init__(self, offset_sec=0, *args, **kwargs):
        super(GitTz, self).__init__(*args, **kwargs)
        self._offset = datetime.timedelta(seconds=offset_sec)

    def utcoffset(self, dt):
        return self._offset

    def dst(self, dt):
        return datetime.timedelta(0)


class GitModifier(object):
    """Stores authorship/committer information"""
    def __init__(self, name=None, email=None, date=None):
        """
        @param name: the modifier's name
        @type name: C{str}
        @param email: the modifier's email
        @type email: C{str}
        @param date: the date of the modification
        @type date: C{str} (git raw date), C{int} (timestamp) or I{datetime} object
        """
        self.name = name
        self.email = email
        self._parse_date(date)

    def _parse_date(self, date):
        self._date = None
        tz = GitTz(0)

        if isinstance(date, six.string_types):
            timestamp, offset = date.split()
            offset_h = int(offset[:-2])
            offset_m = int(offset[-2:])
            tz = GitTz(offset_h * 3600 + offset_m * 60)
            self._date = datetime.datetime.fromtimestamp(int(timestamp), tz)
        elif type(date) in [type(0), type(0.0)]:
            self._date = datetime.datetime.fromtimestamp(date, tz)
        elif isinstance(date, datetime.datetime):
            if date.tzinfo:
                self._date = date
            else:
                self._date = date.replace(tzinfo=tz)
        elif date is not None:
            raise ValueError("Date '%s' not timestamp, "
                             "datetime object or git raw date" % date)

    def _get_env(self, who):
        """Get author or committer information as env var dictionary"""
        who = who.upper()
        if who not in ['AUTHOR', 'COMMITTER']:
            raise GitModifierError("Neither committer nor author")

        extra_env = {}
        if self.name:
            extra_env['GIT_%s_NAME' % who] = self.name
        if self.email:
            extra_env['GIT_%s_EMAIL' % who] = self.email
        if self.date:
            extra_env['GIT_%s_DATE' % who] = self.date
        return extra_env

    def get_date(self):
        """Return date as a git raw date"""
        if self._date:
            return "%s %s" % (calendar.timegm(self._date.utctimetuple()),
                              self._date.strftime('%z'))
        else:
            return None

    def set_date(self, date):
        """Set date from timestamp, git raw date or datetime object"""
        self._parse_date(date)

    date = property(get_date, set_date)

    @property
    def datetime(self):
        """Return the date as datetime object"""
        return self._date

    @property
    def tz_offset(self):
        """Return the date's UTC offset"""
        return self._date.strftime('%z')

    def get_author_env(self):
        """
        Get env vars for authorship information

        >>> g = GitModifier("Joey Ramone", "joey@example.com")
        >>> g.get_author_env()['GIT_AUTHOR_EMAIL']
        'joey@example.com'
        >>> g.get_author_env()['GIT_AUTHOR_NAME']
        'Joey Ramone'

        @return: Author information suitable to use as environment variables
        @rtype: C{dict}
        """
        return self._get_env('author')

    def get_committer_env(self):
        """
        Get env vars for committer information

        >>> g = GitModifier("Joey Ramone", "joey@example.com")
        >>> g.get_committer_env()['GIT_COMMITTER_EMAIL']
        'joey@example.com'
        >>> g.get_committer_env()['GIT_COMMITTER_NAME']
        'Joey Ramone'

        @return: Committer information suitable to use as environment variables
        @rtype: C{dict}
        """
        return self._get_env('committer')

    def __getitem__(self, key):
        if key == 'date':
            return self.date
        else:
            return self.__dict__[key]

    @staticmethod
    def keys():
        return ['name', 'email', 'date']

    def items(self):
        items = []
        for key in self.keys():
            val = self.__getitem__(key)
            if val:
                items.append((key, val))
        return items
