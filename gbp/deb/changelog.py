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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""A Debian Changelog"""

import email
import os
import subprocess

class NoChangeLogError(Exception):
    """No changelog found"""
    pass

class ParseChangeLogError(Exception):
    """Problem parsing changelog"""
    pass

class ChangeLog(object):
    """A Debian changelog"""

    def __init__(self, contents=None, filename=None):
        """
        Parse an existing changelog, Either contents, containing the contents
        of a changelog file, or filename, pointing to a changelog file must be
        passed.
        """
        # Check that either contents or filename is passed (but not both)
        if (not filename and not contents) or (filename and contents):
            raise Exception("Either filename or contents must be passed")

        # If a filename was passed, check if it exists
        if filename and not os.access(filename, os.F_OK):
            raise NoChangeLogError, "Changelog %s not found" % (filename, )

        # If no filename was passed, let's read from stdin
        if not filename:
            filename = '-'

        # Note that if contents is None, stdin will just be closed right
        # away by communicate.
        cmd = subprocess.Popen(['dpkg-parsechangelog', '-l%s' % filename],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        (output, errors) = cmd.communicate(contents)
        if cmd.returncode:
            raise ParseChangeLogError("Failed to parse changelog. "
                                      "dpkg-parsechangelog said:\n%s" % (errors, ))
        # Parse the result of dpkg-parsechangelog (which looks like
        # email headers)
        cp = email.message_from_string(output)
        try:
            if ':' in cp['Version']:
                cp['Epoch'], cp['NoEpoch-Version'] = cp['Version'].split(':', 1)
            else:
                cp['NoEpoch-Version'] = cp['Version']
            if '-' in cp['NoEpoch-Version']:
                cp['Upstream-Version'], cp['Debian-Version'] = cp['NoEpoch-Version'].rsplit('-', 1)
            else:
                cp['Debian-Version'] = cp['NoEpoch-Version']
        except TypeError:
            raise ParseChangeLogError, output.split('\n')[0]

        self._cp = cp

    def __getitem__(self, item):
        return self._cp[item]

    def __setitem__(self, item, value):
        self._cp[item] = value

    @property
    def name(self):
        """The packges name"""
        return self._cp['Source']

    @property
    def version(self):
       """The full version string"""
       return self._cp['Version']

    @property
    def upstream_version(self):
        """The upstream version"""
        return self._cp['Upstream-Version']

    @property
    def debian_version(self):
        """The Debian part of the version number"""
        return self._cp['Debian-Version']

    @property
    def epoch(self):
        """The package's epoch"""
        return self._cp['Epoch']

    @property
    def noepoch(self):
        """The version string without the epoch"""
        return self._cp['NoEpoch-Version']

    def has_epoch(self):
        """
        Whether the version has an epoch

        @return: C{True} if the version has an epoch, C{False} otherwise
        @rtype: C{bool}
        """
        return self._cp.has_key('Epoch')

    def is_native(self):
        """
        Whether this is a native Debian package
        """
        return not '-' in self.version
