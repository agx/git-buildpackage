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
#    along with this program; if not, please see
#    <http://www.gnu.org/licenses/>
# END OF COPYRIGHT #

import subprocess
from setuptools import setup, find_packages
import os


def fetch_version():
    """Get version from debian changelog and write it to gbp/version.py"""
    version = "0.0"

    try:
        popen = subprocess.Popen('dpkg-parsechangelog', stdout=subprocess.PIPE)
        out, ret = popen.communicate()
        for line in out.decode('utf-8').split('\n'):
            if line.startswith('Version:'):
                version = line.split(' ')[1].strip()
                break
    except OSError:
        pass  # Failing is fine, we just can't print the version then

    with open('gbp/version.py', 'w') as f:
        f.write('"The current gbp version number"\n')
        f.write('gbp_version = "%s"\n' % version)

    return version


def readme():
    with open('README.md') as file:
        return file.read()


def setup_requires():
    if os.getenv('WITHOUT_NOSETESTS'):
        return []
    else:
        return ['nose>=0.11.1', 'coverage>=2.85', 'nosexcover>=1.0.7']


setup(name="gbp",
      version=fetch_version(),
      author=u'Guido Günther',
      author_email='agx@sigxcpu.org',
      url='https://honk.sigxcpu.org/piki/projects/git-buildpackage/',
      description='Suite to help with Debian packages in Git repositories',
      license='GPLv2+',
      long_description=readme(),
      classifiers=[
          'Environment :: Console',
          'Programming Language :: Python :: 2',
          'Topic :: Software Development :: Version Control',
          'Operating System :: POSIX :: Linux',
      ],
      scripts=['bin/git-pbuilder',
               'bin/gbp-builder-mock'],
      packages=find_packages(exclude=['tests', 'tests.*']),
      data_files=[("share/git-buildpackage/", ["gbp.conf"]), ],
      requires=["six"],
      setup_requires=setup_requires(),
      entry_points={
          'console_scripts': ['gbp=gbp.scripts.supercommand:supercommand'],
      },
      )
