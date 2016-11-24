# vim: set fileencoding=utf-8 :
#
# (C) 2016 Guido Günther <agx@sigxcpu.org>
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

from tests.component import (ComponentTestBase,
                             ComponentTestGitRepository)
from tests.component.deb import DEB_TEST_DATA_DIR

from nose.tools import ok_

from gbp.scripts.import_dsc import main as import_dsc
from gbp.scripts.clone import main as clone


class TestClone(ComponentTestBase):
    """Test cloning from a remote"""

    def test_clone_nonempty(self):
        """Test that cloning into an existing dir fails"""
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-native',
                                'git-buildpackage_%s.dsc' % version)

        # Build up somethng we can clone from
        dsc = _dsc('0.4.14')
        assert import_dsc(['arg0', dsc]) == 0
        repo = ComponentTestGitRepository('git-buildpackage')
        self._check_repo_state(repo, 'master', ['master'])
        assert len(repo.get_commits()) == 1

        ok_(clone(['arg0', repo.path]) == 1,
            "Cloning did no fail as expected")
        self._check_log(-2, "gbp:error: Git command failed: Error running git clone: fatal: destination path 'git-buildpackage' already exists and is not an empty directory.")

    def test_clone_native(self):
        """Test that cloning of debian native packages works"""
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-native',
                                'git-buildpackage_%s.dsc' % version)

        # Build up somethng we can clone from
        dsc = _dsc('0.4.14')
        assert import_dsc(['arg0', dsc]) == 0
        repo = ComponentTestGitRepository('git-buildpackage')
        self._check_repo_state(repo, 'master', ['master'])
        assert len(repo.get_commits()) == 1

        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        clone(['arg0',
               '--postclone=printenv > postclone.out',
               repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])
        assert len(cloned.get_commits()) == 1
        self.check_hook_vars('postclone', ["GBP_GIT_DIR"])

    def test_clone_environ(self):
        """Test that environment variables influence git configuration"""
        def _dsc(version):
            return os.path.join(DEB_TEST_DATA_DIR,
                                'dsc-native',
                                'git-buildpackage_%s.dsc' % version)

        # Build up somethng we can clone from
        dsc = _dsc('0.4.14')
        os.environ['DEBFULLNAME'] = 'testing tester'
        os.environ['DEBEMAIL'] = 'gbp-tester@debian.invalid'
        assert import_dsc(['arg0', dsc]) == 0
        repo = ComponentTestGitRepository('git-buildpackage')
        self._check_repo_state(repo, 'master', ['master'])
        assert len(repo.get_commits()) == 1

        got = repo.get_config("user.email")
        want = os.environ['DEBEMAIL']
        ok_(got == want, "unexpected git config user.email: got %s, want %s" % (got, want))

        got = repo.get_config("user.name")
        want = os.environ['DEBFULLNAME']
        ok_(got == want, "unexpected git config user.name: got %s, want %s" % (got, want))
