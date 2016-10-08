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
"""Tests for the gbp-rpm-ch tool"""

import os
import re
from nose.tools import assert_raises, eq_, ok_  # pylint: disable=E0611

from gbp.scripts.rpm_ch import main as rpm_ch
from gbp.git import GitRepository
from tests.testutils import capture_stderr

from tests.component.rpm import RpmRepoTestBase

# Disable "Method could be a function warning"
# pylint: disable=R0201


def mock_ch(args):
    """Wrapper for gbp-rpm-ch"""
    with capture_stderr():
        return rpm_ch(['arg0', '--packaging-branch=master',
                       '--spawn-editor=never'] + args)


class TestRpmCh(RpmRepoTestBase):
    """Basic tests for gbp-rpm-ch"""

    def setUp(self):
        """Test case setup"""
        super(TestRpmCh, self).setUp()
        # Set environment so that commits succeed without git config
        os.environ['GIT_AUTHOR_NAME'] = 'My Name'
        os.environ['GIT_COMMITTER_NAME'] = 'My Name'
        os.environ['EMAIL'] = 'me@example.com'

    @staticmethod
    def read_file(filename):
        """Read file to a list"""
        with open(filename) as fobj:
            return fobj.readlines()

    def test_invalid_args(self):
        """See that gbp-rpm-ch fails gracefully when called with invalid args"""
        GitRepository.create('.')

        with assert_raises(SystemExit):
            mock_ch(['--invalid-opt'])

    def test_import_outside_repo(self):
        """Run gbp-rpm-ch when not in a git repository"""
        eq_(mock_ch([]), 1)
        self._check_log(0, 'gbp:error: No Git repository at ')

    def test_update_spec_changelog(self):
        """Test updating changelog in spec"""
        repo = self.init_test_repo('gbp-test')
        eq_(mock_ch([]), 0)
        eq_(repo.status(), {' M': ['gbp-test.spec']})

    def test_update_changes_file(self):
        """Test updating a separate changes file"""
        repo = self.init_test_repo('gbp-test-native')
        eq_(mock_ch([]), 0)
        eq_(repo.status(), {' M': ['packaging/gbp-test-native.changes']})

    def test_create_spec_changelog(self):
        """Test creating changelog in spec file"""
        repo = self.init_test_repo('gbp-test2')
        orig_content = self.read_file('packaging/gbp-test2.spec')

        # Fails if no starting point is given
        eq_(mock_ch([]), 1)
        self._check_log(-1, "gbp:error: Couldn't determine starting point")

        # Give starting point
        eq_(mock_ch(['--since=HEAD^']), 0)
        eq_(repo.status(), {' M': ['packaging/gbp-test2.spec']})
        content = self.read_file('packaging/gbp-test2.spec')
        # Should contain 4 lines (%changelog, header, 1 entry and an empty line)
        eq_(len(content), len(orig_content) + 4)

    def test_create_changes_file(self):
        """Test creating a separate changes file"""
        repo = self.init_test_repo('gbp-test2')

        # Fails if no starting point is given
        eq_(mock_ch(['--changelog-file=CHANGES']), 1)
        self._check_log(-1, "gbp:error: Couldn't determine starting point")

        # Give starting point
        eq_(mock_ch(['--since=HEAD^', '--changelog-file=CHANGES']), 0)
        eq_(repo.status(), {'??': ['packaging/gbp-test2.changes']})
        content = self.read_file('packaging/gbp-test2.changes')
        # Should contain 3 lines (header, 1 entry and an empty line)
        eq_(len(content), 3)

    def test_option_changelog_file(self):
        """Test the --changelog-file cmdline option"""
        repo = self.init_test_repo('gbp-test-native')

        # Guess changelog file
        eq_(mock_ch(['--changelog-file=CHANGES']), 0)
        eq_(repo.status(), {' M': ['packaging/gbp-test-native.changes']})

        # Use spec file as changelog
        eq_(mock_ch(['--changelog-file=SPEC', '--since=HEAD^']), 0)
        eq_(repo.status(), {' M': ['packaging/gbp-test-native.changes',
                                   'packaging/gbp-test-native.spec']})

        # Arbitrary name
        eq_(mock_ch(['--changelog-file=foo.changes', '--since=HEAD^']), 0)
        eq_(repo.status(), {' M': ['packaging/gbp-test-native.changes',
                                   'packaging/gbp-test-native.spec'],
                            '??': ['foo.changes']})

    def test_option_spec_file(self):
        """Test the --spec-file cmdline option"""
        repo = self.init_test_repo('gbp-test2')

        eq_(mock_ch(['--spec-file=foo.spec']), 1)
        self._check_log(-1, "gbp:error: Unable to read spec file")

        eq_(mock_ch(['--spec-file=']), 1)
        self._check_log(-1, "gbp:error: Multiple spec files found")

        eq_(mock_ch(['--spec-file=packaging/gbp-test2.spec', '--since=HEAD^']),
            0)
        eq_(repo.status(), {' M': ['packaging/gbp-test2.spec']})

    def test_option_packaging_dir(self):
        """Test the --packaging-dir cmdline option"""
        repo = self.init_test_repo('gbp-test-native')

        eq_(mock_ch(['--packaging-dir=foo']), 1)
        self._check_log(-1, "gbp:error: No spec file found")

        # Packaging dir should be taken from spec file if it is defined
        eq_(mock_ch(['--packaging-dir', 'foo', '--spec-file',
                     'packaging/gbp-test-native.spec']), 0)
        eq_(repo.status(), {' M': ['packaging/gbp-test-native.changes']})

    def test_branch_options(self):
        """Test the --packaging-branch and --ignore-branch cmdline options"""
        self.init_test_repo('gbp-test-native')

        eq_(mock_ch(['--packaging-branch=foo']), 1)
        self._check_log(-2, "gbp:error: You are not on branch 'foo'")

        eq_(mock_ch(['--packaging-branch=foo', '--ignore-branch']), 0)

    def test_option_no_release(self):
        """Test the --no-release cmdline option"""
        self.init_test_repo('gbp-test-native')
        orig_content = self.read_file('packaging/gbp-test-native.changes')

        eq_(mock_ch(['--no-release']), 0)
        content = self.read_file('packaging/gbp-test-native.changes')
        # Only one line (entry) added
        eq_(len(content), len(orig_content) + 1)

    def test_author(self):
        """Test determining the author name/email"""
        repo = self.init_test_repo('gbp-test-native')

        # Test taking email address from env
        os.environ['EMAIL'] = 'user@host.com'
        eq_(mock_ch([]), 0)
        header = self.read_file('packaging/gbp-test-native.changes')[0]
        ok_(re.match(r'.+ <user@host\.com> .+', header))

        # Missing git config setting should not cause a failure
        del os.environ['EMAIL']
        del os.environ['GIT_AUTHOR_NAME']
        os.environ['GIT_CONFIG_NOSYSTEM'] = '1'
        os.environ['HOME'] = os.path.abspath('.')
        eq_(mock_ch(['--git-author', '--since=HEAD^1']), 0)

        # Test the --git-author option
        saved_author = os.environ.get('GIT_AUTHOR_NAME')
        saved_email = os.environ.get('GIT_AUTHOR_EMAIL')
        os.environ['GIT_AUTHOR_NAME'] = 'John Doe'
        os.environ['GIT_AUTHOR_EMAIL'] = 'jd@host.com'
        with open(os.path.join(repo.git_dir, 'config'), 'a') as fobj:
            fobj.write('[user]\n  name=John Doe\n  email=jd@host.com\n')
        eq_(mock_ch(['--git-author', '--since=HEAD^']), 0)
        header = self.read_file('packaging/gbp-test-native.changes')[0]
        ok_(re.match(r'.+ John Doe <jd@host\.com> .+', header), header)
        if saved_author:
            os.environ['GIT_AUTHOR_NAME'] = saved_author
        if saved_email:
            os.environ['GIT_AUTHOR_EMAIL'] = saved_email

    def test_option_full(self):
        """Test the --full cmdline option"""
        repo = self.init_test_repo('gbp-test-native')
        orig_content = self.read_file('packaging/gbp-test-native.changes')

        eq_(mock_ch(['--full', '--since=HEAD^']), 0)
        commit_msg_body = repo.get_commit_info('HEAD')['body']
        full_msg = [line for line in commit_msg_body.splitlines() if line]
        content = self.read_file('packaging/gbp-test-native.changes')
        # New lines: header, 1 entry "header", entry "body" from commit message
        # and one empty line
        eq_(len(content), len(orig_content) + 3 + len(full_msg))

    def test_option_ignore_regex(self):
        """Test the --ignore-regex cmdline option"""
        repo = self.init_test_repo('gbp-test-native')
        orig_content = self.read_file('packaging/gbp-test-native.changes')

        eq_(mock_ch(['--full', '--since', 'HEAD^', '--ignore-regex',
                     'Signed-off-by:.*']), 0)
        commit_msg_body = repo.get_commit_info('HEAD')['body']
        full_msg = [line for line in commit_msg_body.splitlines() if
                    (line and not line.startswith('Signed-off-by:'))]
        content = self.read_file('packaging/gbp-test-native.changes')
        # New lines: header, 1 entry "header", filtered entry "body" from
        # commit message and one empty line
        eq_(len(content), len(orig_content) + 3 + len(full_msg))

    def test_option_id_len(self):
        """Test the --id-len cmdline option"""
        repo = self.init_test_repo('gbp-test-native')

        eq_(mock_ch(['--id-len=10']), 0)
        commit_id = repo.rev_parse('HEAD', 10)
        content = self.read_file('packaging/gbp-test-native.changes')
        ok_(content[1].startswith('- [%s] ' % commit_id))

    def test_option_changelog_revision(self):
        """Test the --id-len cmdline option"""
        self.init_test_repo('gbp-test-native')

        # Test invalid format (unknown field)
        eq_(mock_ch(['--changelog-revision=%(unknown_field)s']), 1)
        self._check_log(-1, 'gbp:error: Unable to construct revision field')

        # Test acceptable format
        eq_(mock_ch(['--changelog-revision=foobar']), 0)
        header = self.read_file('packaging/gbp-test-native.changes')[0]
        ok_(re.match(r'.+ foobar$', header))

    def test_option_editor_cmd(self):
        """Test the --editor-cmd and --spawn-editor cmdline options"""
        repo = self.init_test_repo('gbp-test-native')
        eq_(mock_ch(['--spawn-editor=release', '--editor-cmd=rm']), 0)
        eq_(repo.status(), {' D': ['packaging/gbp-test-native.changes']})

        repo.force_head('HEAD', hard=True)
        ok_(repo.is_clean())

        os.environ['EDITOR'] = 'rm'
        eq_(mock_ch(['--spawn-editor=always', '--editor-cmd=']),
            0)

    def test_user_customizations(self):
        """Test the user customizations"""
        repo = self.init_test_repo('gbp-test-native')

        # Non-existent customization file
        eq_(mock_ch(['--customizations=customizations.py']), 1)

        # Create user customizations file
        with open('customizations.py', 'w') as fobj:
            fobj.write("class ChangelogEntryFormatter(object):\n")
            fobj.write("    @classmethod\n")
            fobj.write("    def compose(cls, commit_info, **kwargs):\n")
            fobj.write("        return ['- %s' % commit_info['id']]\n")

        eq_(mock_ch(['--customizations=customizations.py']), 0)
        entry = self.read_file('packaging/gbp-test-native.changes')[1]
        sha = repo.rev_parse('HEAD')
        eq_(entry, '- %s\n' % sha)

    def test_paths(self):
        """Test tracking of certain paths only"""
        repo = self.init_test_repo('gbp-test-native')
        orig_content = self.read_file('packaging/gbp-test-native.changes')

        # Add new commit with known content
        with open('new-file.txt', 'w') as fobj:
            fobj.write('this is new content\n')
        repo.add_files('new-file.txt')
        repo.commit_staged('Add new file')

        # Only track a non-existent file
        eq_(mock_ch(['--since=HEAD^', 'non-existent-path']), 0)
        content = self.read_file('packaging/gbp-test-native.changes')
        # New lines: header and one empty line, no entries
        eq_(len(content), len(orig_content) + 2)

        # Track existing file
        repo.force_head('HEAD', hard=True)
        eq_(mock_ch(['--since=HEAD^', 'new-file.txt']), 0)
        content = self.read_file('packaging/gbp-test-native.changes')
        # New lines: header, one entry line and one empty line
        eq_(len(content), len(orig_content) + 3)

    def test_commit_guessing(self):
        """Basic tests for guessing the starting point"""
        repo = self.init_test_repo('gbp-test-native')

        # Check 'tagname' that is not found
        eq_(mock_ch(['--changelog-revision=%(tagname)s']), 0)
        self._check_log(0, 'gbp:warning: Changelog points to tagname')

        # Check 'upstreamversion' and 'release' fields
        repo.force_head('HEAD', hard=True)
        eq_(mock_ch(['--changelog-revision=%(upstreamversion)s-%(release)s']),
            0)

    def test_commit_guessing_fail(self):
        """Test for failure of start commit guessing"""
        self.init_test_repo('gbp-test-native')

        # Add "very old" header to changelog
        with open('packaging/gbp-test-native.changes', 'w') as ch_fp:
            ch_fp.write('* Sat Jan 01 2000 User <user@host.com> 123\n- foo\n')
        # rpm-ch should fail by not being able to find any commits before the
        # last changelog section
        eq_(mock_ch([]), 1)
        self._check_log(-1, "gbp:error: Couldn't determine starting point")
