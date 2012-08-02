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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Interface to uscan"""

import os, re, subprocess

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
        >>> u._parse('<status>up to date</status>')
        >>> u.tarball
        >>> u.uptodate
        True
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

        if "<status>up to date</status>" in out:
            self._uptodate = True
            self._tarball = None
            return
        else:
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
                            m = re.match("<%s>(.*)</%s>" % (n,n), row)
                            if m:
                                d[n] = m.group(1)
                    d["ext"] = os.path.splitext(d['upstream-url'])[1]
                    # We want the name of the orig tarball if possible
                    source = ("../%(package)s_%(upstream-version)s."
                              "orig.tar%(ext)s" % d)

                    # Fall back to the upstream source name otherwise
                    if not os.path.exists(source):
                        source = "../%s" % d['upstream-url'].rsplit('/',1)[1]
                        if not os.path.exists(source):
                            raise UscanError("Couldn't find tarball at '%s'" %
                                         source)
                except KeyError as e:
                    raise UscanError("Couldn't find '%s' in uscan output" %
                                     e.args[0])
            self._tarball = source

    def scan(self, destdir='..'):
        """Invoke uscan to fetch a new upstream version"""
        p = subprocess.Popen(['uscan', '--symlink', '--destdir=%s' % destdir,
                              '--dehs'],
                             cwd=self._dir,
                             stdout=subprocess.PIPE)
        out = p.communicate()[0]
        return self._parse(out)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
