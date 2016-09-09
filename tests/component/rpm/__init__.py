# vim: set fileencoding=utf-8 :
#
# (C) 2012 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""Test module for RPM command line tools of the git-buildpackage suite"""

from nose.tools import nottest
import os
import shutil
from glob import glob

from gbp.command_wrappers import Command

from tests.component import ComponentTestBase, ComponentTestGitRepository


RPM_TEST_DATA_SUBMODULE = os.path.join('tests', 'component', 'rpm', 'data')
RPM_TEST_DATA_DIR = os.path.abspath(RPM_TEST_DATA_SUBMODULE)


def setup():
    """Test Module setup"""
    ComponentTestGitRepository.check_testdata(RPM_TEST_DATA_SUBMODULE)


class RpmRepoTestBase(ComponentTestBase):
    """Baseclass for tests run in a Git repository with packaging data"""

    @classmethod
    def setUpClass(cls):
        """Initializations only made once per test run"""
        super(RpmRepoTestBase, cls).setUpClass()

        # Initialize test data repositories
        cmd = Command('./manage.py', cwd=RPM_TEST_DATA_DIR, capture_stderr=True)
        cmd(['import-repo', '-o', cls._tmproot])

        cls.orig_repos = {}
        for path in glob(cls._tmproot + '/*.repo'):
            prj = os.path.basename(path).rsplit('.', 1)[0]
            cls.orig_repos[prj] = ComponentTestGitRepository(path)

    @classmethod
    @nottest
    def init_test_repo(cls, pkg_name):
        """Initialize git repository for testing"""
        dirname = os.path.basename(cls.orig_repos[pkg_name].path)
        shutil.copytree(cls.orig_repos[pkg_name].path, dirname)
        os.chdir(dirname)
        return ComponentTestGitRepository('.')

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
