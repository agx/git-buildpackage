#!/usr/bin/python
# vim: set fileencoding=utf-8 :
# Copyright (C) 2006-2011 Guido Günther <agx@sigxcpu.org>
#
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
# END OF COPYRIGHT #

import subprocess
from setuptools import setup, find_packages


def fetch_version():
    """Get version from debian changelog and write it to gbp/version.py"""
    version = "0.0"

    try:
        popen = subprocess.Popen('dpkg-parsechangelog', stdout=subprocess.PIPE)
        out, ret = popen.communicate()
        for line in out.split('\n'):
            if line.startswith('Version:'):
                version = line.split(' ')[1].strip()
                break
    except OSError:
        pass # Failing is fine, we just can't print the version then

    with file('gbp/version.py', 'w') as f:
        f.write('gbp_version="%s"\n' % version)

    return version


setup(name = "gbp",
      version = fetch_version(),
      author = u'Guido Günther',
      author_email = 'agx@sigxcpu.org',
      scripts = [ 'bin/git-buildpackage',
                  'bin/git-import-dsc',
                  'bin/git-import-orig',
                  'bin/git-dch',
                  'bin/git-import-dscs',
                  'bin/gbp-pq',
                  'bin/gbp-pull',
                  'bin/gbp-clone',
                  'bin/gbp-create-remote-repo',
                  'bin/git-pbuilder'],
      packages = find_packages(exclude=['tests', 'tests.*']),
      data_files = [("/etc/git-buildpackage/", ["gbp.conf"]),],
      setup_requires=['nose>=0.11.1', 'coverage>=2.85'],
)
