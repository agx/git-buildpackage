# vim: set fileencoding=utf-8 :
#
# (C) 2017 Guido Günther <agx@sigxcpu.org>
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

from tests.component import ComponentTestBase
from tests.component.deb import DEB_TEST_DATA_DIR
from tests.component.deb.fixtures import RepoFixtures
from tests.testutils import skip_without_cmd

import gbp.scripts.dch
from gbp.scripts.dch import main as dch

from nose.tools import eq_, ok_


def _dsc_file(pkg, version, dir='dsc-3.0'):
    return os.path.join(DEB_TEST_DATA_DIR, dir, '%s_%s.dsc' % (pkg, version))


DEFAULT_DSC = _dsc_file('hello-debhelper', '2.6-2')


@skip_without_cmd('debchange')
class TestDch(ComponentTestBase):
    """Test importing of new upstream versions"""
    pkg = "hello-debhelper"
    def_branches = ['master', 'upstream', 'pristine-tar']

    @RepoFixtures.quilt30(DEFAULT_DSC)
    def test_user_customizations(self, repo):
        os.chdir(repo.path)
        # Non-existent customization file
        ok_(dch(['arg0', '--customizations=customizations.py']) == 1,
            "dch did no fail as expected")

        # Create user customizations file
        with open('customizations.py', 'w') as fobj:
            fobj.write("""def format_changelog_entry(commit_info, options, last_commit=False):
    return ['testentry']
""")
        # Add the file so we have a change
        repo.add_files(['customizations.py'])
        repo.commit_all(msg="test customizations")
        ok_(dch(['arg0', '-S', '-a', '--customizations=customizations.py']) == 0,
            "dch did no succeed as expected")
        with open("debian/changelog", encoding='utf-8') as f:
            cl = f.read()
        ok_('* testentry\n' in cl)
        del gbp.scripts.dch.user_customizations['format_changelog_entry']

    @RepoFixtures.native()
    def test_postedit_hook(self, repo):
        os.chdir(repo.path)
        eq_(dch(['arg0', '-N', '1.2.3', '--postedit', 'echo $GBP_DEBIAN_VERSION > foo.txt']), 0)
        with open('foo.txt') as f:
            eq_(f.read(), '1.2.3\n')
