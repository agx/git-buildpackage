# vim: set fileencoding=utf-8 :
#
# (C) 2021 Andrej Shadura <andrew@shadura.me>
# (C) 2021 Collabora Limited
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
from tests.component.deb.fixtures import RepoFixtures

from nose.tools import ok_

from gbp.scripts.clone import main as clone
from gbp.scripts.setup_gitattributes import main as setup_gitattributes


sorted_gitattrs = [
    '# Added by git-buildpackage to disable .gitattributes found in the upstream tree',
    '* -export-ignore',
    '* -export-subst',
    '* dgit-defuse-attrs',
    '[attr]dgit-defuse-attrs  -text -eol -crlf -ident -filter -working-tree-encoding',
]


dgit_attributes = [
    '*\tdgit-defuse-attrs',
    '[attr]dgit-defuse-attrs\t-text -eol -crlf -ident -filter -working-tree-encoding',
    '# ^ see GITATTRIBUTES in dgit(7) and dgit setup-new-tree in dgit(1)'
]


dgit34_attributes = [
    '*\tdgit-defuse-attrs',
    '[attr]dgit-defuse-attrs\t-text -eol -crlf -ident -filter',
    '# ^ see dgit(7).  To undo, leave a definition of [attr]dgit-defuse-attrs'
]


class TestSetupGitattributes(ComponentTestBase):
    """Test setting up Git attributes"""

    @RepoFixtures.native()
    def test_setup_gitattrs_do_nothing(self, repo):
        """Test that disabling all knows presets works and gives an error"""
        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        clone(['arg0',
               repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])

        attrs_file = os.path.join(dest, '.git', 'info', 'attributes')

        # file shouldn’t exist at this point yet
        self.assertFalse(os.path.exists(attrs_file) and os.path.getsize(attrs_file),
                         "%s is non-empty" % attrs_file)

        os.chdir(cloned.path)
        setup_gitattributes(['arg0', '--no-dgit-defuse-attrs'])

        # file shouldn’t exist at this point yet
        self.assertFalse(os.path.exists(attrs_file) and os.path.getsize(attrs_file),
                         "%s is non-empty" % attrs_file)

        self._check_log(-1,
                        "gbp:error: Nothing to do, no settings to apply.")

    @RepoFixtures.native()
    def test_setup_gitattrs(self, repo):
        """Test that setting up Git attributes manually works"""
        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        clone(['arg0',
               repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])

        attrs_file = os.path.join(dest, '.git', 'info', 'attributes')

        # file shouldn’t exist at this point yet
        self.assertFalse(os.path.exists(attrs_file) and os.path.getsize(attrs_file),
                         "%s is non-empty" % attrs_file)

        os.chdir(cloned.path)
        setup_gitattributes(['arg0'])

        ok_(os.path.exists(attrs_file), "%s is missing" % attrs_file)

        with open(attrs_file) as f:
            attrs = sorted(f.read().splitlines())
        self.assertEqual(attrs, sorted_gitattrs)

    @RepoFixtures.native()
    def test_setup_gitattrs_dgit(self, repo):
        """Test that setting up Git attributes manually works even with dgit"""
        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        clone(['arg0',
               repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])

        attrs_file = os.path.join(dest, '.git', 'info', 'attributes')

        # file shouldn’t exist at this point yet
        self.assertFalse(os.path.exists(attrs_file) and os.path.getsize(attrs_file),
                         "%s is non-empty" % attrs_file)

        with open(attrs_file, 'w') as f:
            f.write('\n'.join(dgit_attributes))

        os.chdir(cloned.path)
        setup_gitattributes(['arg0', '--verbose'])

        ok_(os.path.exists(attrs_file), "%s is missing" % attrs_file)

        with open(attrs_file) as f:
            attrs = sorted(f.read().splitlines())

        expected_gitattrs = sorted(sorted_gitattrs + [
            '# Old dgit macro disabled:',
            '# [attr]dgit-defuse-attrs\t-text -eol -crlf -ident -filter -working-tree-encoding',
            '# ^ see GITATTRIBUTES in dgit(7) and dgit setup-new-tree in dgit(1)',
        ])

        self.assertEqual(attrs, expected_gitattrs)

    @RepoFixtures.native()
    def test_setup_gitattrs_dgit34(self, repo):
        """Test that setting up Git attributes manually works even with a very old dgit"""
        dest = os.path.join(self._tmpdir,
                            'cloned_repo')
        clone(['arg0',
               repo.path, dest])
        cloned = ComponentTestGitRepository(dest)
        self._check_repo_state(cloned, 'master', ['master'])

        attrs_file = os.path.join(dest, '.git', 'info', 'attributes')

        # file shouldn’t exist at this point yet
        self.assertFalse(os.path.exists(attrs_file) and os.path.getsize(attrs_file),
                         "%s is non-empty" % attrs_file)

        with open(attrs_file, 'w') as f:
            f.write('\n'.join(dgit34_attributes))

        os.chdir(cloned.path)
        setup_gitattributes(['arg0', '--verbose'])

        ok_(os.path.exists(attrs_file), "%s is missing" % attrs_file)

        with open(attrs_file) as f:
            attrs = sorted(f.read().splitlines())

        expected_gitattrs = sorted(sorted_gitattrs + [
            '# Old dgit macro disabled:',
            '# [attr]dgit-defuse-attrs\t-text -eol -crlf -ident -filter',
            '# ^ see dgit(7).  To undo, leave a definition of [attr]dgit-defuse-attrs',
        ])

        self.assertEqual(attrs, expected_gitattrs)
