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
"""Interface to uscan"""

import os
import re
import subprocess


class UscanError(Exception):
    pass


class Uscan(object):
    cmd = '/usr/bin/uscan'

    def __init__(self, dir='.'):
        self._uptodate = False
        self._tarball = None
        self._dir = os.path.abspath(dir)

    @property
    def uptodate(self):
        return self._uptodate

    @property
    def tarball(self):
        return self._tarball

    def _parse(self, out):
        r"""
        Parse the uscan output return and update the object's properties

        @param out: uscan output
        @type out: string

        >>> u = Uscan('http://example.com/')
        >>> u._parse('<target>virt-viewer_0.4.0.orig.tar.gz</target>')
        >>> u.tarball
        '../virt-viewer_0.4.0.orig.tar.gz'
        >>> u.uptodate
        False
        >>> u._parse('')
        Traceback (most recent call last):
        ...
        UscanError: Couldn't find 'upstream-url' in uscan output
        """
        source = None
        self._uptodate = False

        # Check if uscan downloaded something
        for row in out.split("\n"):
            # uscan >= 2.10.70 has a target element:
            m = re.match(r"<target>(.*)</target>", row)
            if m:
                source = '../%s' % m.group(1)
                break
            elif row.startswith('<messages>'):
                m = re.match(r".*symlinked ([^\s]+) to it", row)
                if m:
                    source = "../%s" % m.group(1)
                    break
                m = re.match(r"Successfully downloaded updated package "
                             "([^<]+)", row)
                if m:
                    source = "../%s" % m.group(1)
                    break
        # Try to determine the already downloaded sources name
        else:
            d = {}

            try:
                for row in out.split("\n"):
                    for n in ('package',
                              'upstream-version',
                              'upstream-url'):
                        m = re.match("<%s>(.*)</%s>" % (n, n), row)
                        if m:
                            d[n] = m.group(1)
                d["ext"] = os.path.splitext(d['upstream-url'])[1]
                # We want the name of the orig tarball if possible
                source = ("../%(package)s_%(upstream-version)s."
                          "orig.tar%(ext)s" % d)

                # Fall back to the upstream source name otherwise
                if not os.path.exists(source):
                    source = "../%s" % d['upstream-url'].rsplit('/', 1)[1]
                    if not os.path.exists(source):
                        raise UscanError("Couldn't find tarball at '%s'" %
                                         source)
            except KeyError as e:
                raise UscanError("Couldn't find '%s' in uscan output" %
                                 e.args[0])
        self._tarball = source

    def _parse_uptodate(self, out):
        """
        Check if the uscan reports that we're up to date.

        @param out: uscan output
        @type out: string

        >>> u = Uscan('http://example.com/')
        >>> u._parse_uptodate('<status>up to date</status>')
        >>> u.tarball
        >>> u.uptodate
        True
        >>> u._parse_uptodate('')
        >>> u.tarball
        >>> u.uptodate
        False
        """
        if "<status>up to date</status>" in out:
            self._uptodate = True
        else:
            self._uptodate = False

    def _raise_error(self, out):
        r"""
        Parse the uscan output for errors and warnings and raise
        a L{UscanError} exception based on this. If no error detail
        is found a generic error message is used.

        @param out: uscan output
        @type out: string
        @raises UscanError: exception raised

        >>> u = Uscan('http://example.com/')
        >>> u._raise_error("<warnings>uscan warning: "
        ... "In watchfile debian/watch, reading webpage\n"
        ... "http://a.b/ failed: 500 Cant connect "
        ... "to example.com:80 (Bad hostname)</warnings>")
        Traceback (most recent call last):
        ...
        UscanError: Uscan failed: uscan warning: In watchfile debian/watch, reading webpage
        http://a.b/ failed: 500 Cant connect to example.com:80 (Bad hostname)
        >>> u._raise_error("<errors>uscan: Can't use --verbose if "
        ... "you're using --dehs!</errors>")
        Traceback (most recent call last):
        ...
        UscanError: Uscan failed: uscan: Can't use --verbose if you're using --dehs!
        >>> u = u._raise_error('')
        Traceback (most recent call last):
        ...
        UscanError: Uscan failed - debug by running 'uscan --verbose'
        """
        msg = None

        for n in ('errors', 'warnings'):
            m = re.search("<%s>(.*)</%s>" % (n, n), out, re.DOTALL)
            if m:
                msg = "Uscan failed: %s" % m.group(1)
                break

        if not msg:
            msg = "Uscan failed - debug by running 'uscan --verbose'"
        raise UscanError(msg)

    def scan(self, destdir='..'):
        """Invoke uscan to fetch a new upstream version"""
        p = subprocess.Popen(['uscan', '--symlink', '--destdir=%s' % destdir,
                              '--dehs'],
                             cwd=self._dir,
                             stdout=subprocess.PIPE)
        out = p.communicate()[0]
        # uscan exits with 1 in case of uptodate and when an error occurred.
        # Don't fail in the uptodate case:
        self._parse_uptodate(out)
        if not self.uptodate:
            if p.returncode:
                self._raise_error(out)
            else:
                self._parse(out)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
