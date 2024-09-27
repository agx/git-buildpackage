#!/usr/bin/python3
# vim: set fileencoding=utf-8 :
# Copyright (C) 2006-2024 Guido Günther <agx@sigxcpu.org>
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

import os
import re
from setuptools import setup

VERSION_PY_PATH = 'gbp/version.py'


def _parse_changelog():
    """Get version from debian changelog and write it to gbp/version.py"""
    with open("debian/changelog", encoding="utf-8") as f:
        line = f.readline()

    # Parse version from changelog without external tooling so it can work
    # on non Debian systems.
    m = re.match(".* \\(([0-9a-zA-Z.~\\-:+]+)\\) ", line)
    if m:
        return m.group(1)

    raise ValueError('Could not parse version from debian/changelog')


def _save_version_py(version):
    with open(VERSION_PY_PATH, 'w') as f:
        f.write('"The current gbp version number"\n')
        f.write('gbp_version = "%s"\n' % version)


def _load_version():
    with open(VERSION_PY_PATH, 'r') as f:
        version_py = f.read()
    version_py_globals = {}
    exec(version_py, version_py_globals)
    return version_py_globals['gbp_version']


def parse_and_fetch_version():
    if os.path.exists('debian/changelog'):
        version = _parse_changelog()
        _save_version_py(version)
        # we could return with the version here, but instead we check that
        # the file has been properly written and it can be loaded back

    version = _load_version()
    return version


def setup_requires():
    if os.getenv('WITHOUT_PYTESTS'):
        return []
    else:
        return ['pytest', 'coverage>=2.85']


setup(name="gbp",
      version=parse_and_fetch_version(),
      setup_requires=setup_requires(),
      )
