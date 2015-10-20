# vim: set fileencoding=utf-8 :
#
# (C) 2013-2015 Intel Corporation <markus.lehtonen@linux.intel.com>
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
#
"""Unit tests for the gbp-buildpackage-rpm tool"""

import glob
import mock
import os
import re
import shutil
import stat
import subprocess

from nose.tools import assert_raises, eq_, ok_ # pylint: disable=E0611
from nose.plugins.skip import SkipTest

from gbp.git import GitRepository
from gbp.scripts.buildpackage_rpm import main as gbp_rpm
from tests.component.rpm import RpmRepoTestBase, RPM_TEST_DATA_DIR
from tests.testutils import ls_dir, ls_tar

# Disable "Method could be a function warning"
#   pylint: disable=R0201
# Disable "Too many public methods"
#   pylint: disable=R0904


DATA_DIR = os.path.join(RPM_TEST_DATA_DIR, 'rpm')
ORIG_DATA_DIR = os.path.join(RPM_TEST_DATA_DIR, 'orig')

MOCK_NOTIFICATIONS = []


def mock_gbp(args):
    """Wrapper for gbp-buildpackage-rpm"""
    return gbp_rpm(['arg0', '--git-notify=off','--git-ignore-branch']
                   + args
                   + ['-ba', '--clean', '--target=noarch', '--nodeps'])

def mock_notify(summary, message, notify_opt):
    """Mock notification system"""
    # Auto will succeed
    if notify_opt.is_auto():
        MOCK_NOTIFICATIONS.append((summary, message))
        return True
    # Otherwise fail
    return False


class TestGbpRpm(RpmRepoTestBase):
    """Basic tests for gbp buildpackage-rpm"""

    @staticmethod
    def ls_rpm(rpm):
        """List the contents of an rpm package"""
        args = ['rpm', '-q', '--qf',
                '[%{FILEDIGESTS %{FILEMODES} %{FILENAMES}\n]', '-p']
        popen = subprocess.Popen(args + [rpm], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        stdout, stderr = popen.communicate()
        if popen.returncode:
            raise Exception("Failed to get file metadata for %s: %s" %
                            (rpm, stderr))
        return sorted([(nam, mod, dig) for dig, mod, nam in
                        [lin.split(None, 2) for lin in stdout.splitlines()]])

    @staticmethod
    def check_rpms(directory):
        """Check build results"""
        # Only check files, at least for now
        files = glob.glob(directory + '/*rpm')
        assert files, "No rpms (%s)found in %s" % (files, directory)
        for path in files:
            ref_file = os.path.join(DATA_DIR, os.path.basename(path))
            eq_(TestGbpRpm.ls_rpm(path), TestGbpRpm.ls_rpm(ref_file))

    @staticmethod
    def check_and_rm_file(filepath, content):
        """Check file content and remove it"""
        with open(filepath) as fobj:
            eq_(fobj.read(), content)
        os.unlink(filepath)

    @classmethod
    def setup_class(cls, **kwargs):
        """Setup unit tests"""
        raise SkipTest("Adjust test repo data refs")
        super(TestGbpRpm, cls).setup_class(**kwargs)

    def test_outside_repo(self):
        """Run outside a git repository"""
        eq_(mock_gbp([]), 1)
        self._check_log(0, 'gbp:error: %s is not a git repository' %
                            os.path.abspath('.'))

    def test_invalid_config_file(self):
        """Test invalid config file"""
        # Create and commit dummy invalid config file
        repo = GitRepository.create('.')
        with open('.gbp.conf', 'w') as conffd:
            conffd.write('foobar\n')
        repo.add_files('.gbp.conf')
        repo.commit_all('Add conf')
        eq_(mock_gbp([]), 1)
        self._check_log(0, 'gbp:error: File contains no section headers.')

    def test_native_build(self):
        """Basic test of native pkg"""
        self.init_test_repo('gbp-test-native')
        eq_(mock_gbp([]), 0)
        c = os.path.abspath(os.path.curdir)
        self.check_rpms('../rpmbuild/RPMS/*')
        shutil.rmtree('../rpmbuild')

        """Test --git-cleaner option"""
        self.init_test_repo('gbp-test-native')

        # Make repo dirty
        with open('untracked-file', 'w') as fobj:
            fobj.write('this file is not tracked\n')

        # Build on dirty repo should fail
        eq_(mock_gbp([]), 1)

        # Build should succeed with cleaner
        eq_(mock_gbp(['--git-cleaner=rm untracked-file']), 0)

