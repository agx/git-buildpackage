# vim: set fileencoding=utf-8 :
#
# (C) 2012,2017 Guido Günther <agx@sigxcpu.org>
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
        Parse the uscan output and update the object's properties

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
        gbp.deb.uscan.UscanError: Couldn't find source in uscan output
        """
        source = None
        self._uptodate = False

        for row in out.split("\n"):
            m = re.match(r"<target>(.*)</target>", row)
            if m:
                source = '../%s' % m.group(1)
        if not source:
            raise UscanError("Couldn't find source in uscan output")
        self._tarball = source

    def _parse_uptodate(self, out):
        """
        Check if the uscan reports that we're up to date.

        @param out: uscan output
        @type out: string
        @returns: C{True} if package is up-to-date

        >>> u = Uscan('http://example.com/')
        >>> u._parse_uptodate('<status>up to date</status>')
        True
        >>> u.tarball
        >>> u.uptodate
        True
        >>> u._parse_uptodate('')
        False
        >>> u.tarball
        >>> u.uptodate
        False
        """
        if "<status>up to date</status>" in out:
            self._uptodate = True
        else:
            self._uptodate = False
        return self._uptodate

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
        ... "http://a.b/ failed: 500 Can't connect "
        ... "to example.com:80 (Bad hostname)</warnings>")
        Traceback (most recent call last):
        ...
        gbp.deb.uscan.UscanError: Uscan failed: uscan warning: In watchfile debian/watch, reading webpage
        http://a.b/ failed: 500 Can't connect to example.com:80 (Bad hostname)
        >>> u._raise_error("<errors>uscan: Can't use --verbose if "
        ... "you're using --dehs!</errors>")
        Traceback (most recent call last):
        ...
        gbp.deb.uscan.UscanError: Uscan failed: uscan: Can't use --verbose if you're using --dehs!
        >>> u = u._raise_error('')
        Traceback (most recent call last):
        ...
        gbp.deb.uscan.UscanError: Uscan failed - debug by running 'uscan --verbose'
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

    def scan(self, destdir='..', download_version=None):
        """
        Invoke uscan to fetch a new upstream version

        @returns: C{True} if a new version was downloaded
        """
        cmd = ['uscan', '--symlink', '--destdir=%s' % destdir, '--dehs']
        if download_version:
            cmd += ['--download-version', download_version]
        p = subprocess.Popen(cmd, cwd=self._dir, stdout=subprocess.PIPE)
        out = p.communicate()[0].decode()
        # uscan exits with 1 in case of up-to-date and when an error occurred.
        # Don't fail in the up-to-date case:
        if self._parse_uptodate(out):
            return False

        if p.returncode:
            self._raise_error(out)

        self._parse(out)
        return True

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
