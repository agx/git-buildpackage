# vim: set fileencoding=utf-8 :
#
# (C) 2012 Intel Corporation <markus.lehtonen@linux.intel.com>
# (C) 2013 Guido Günther <agx@sigxcpu.org>
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

import os

from tests.component import ComponentTestGitRepository

DEB_TEST_SUBMODULE = os.path.join('tests', 'component', 'deb', 'data')
DEB_TEST_DATA_DIR = os.path.abspath(DEB_TEST_SUBMODULE)
DEB_TEST_DOWNLOAD_URL = 'https://git.sigxcpu.org/cgit/gbp/deb-testdata/plain/'


def setup():
    """Test Module setup"""
    ComponentTestGitRepository.check_testdata(DEB_TEST_SUBMODULE)
