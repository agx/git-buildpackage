# vim: set fileencoding=utf-8 :
# (C) 2013 Guido Günther <agx@sigxcpu.org>
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
"""Test L{gbp.pq}"""

from . import context
from . import testutils

import os

from gbp.deb.source import DebianSource, DebianSourceError
from gbp.deb.format import DebianSourceFormat
from gbp.git.vfs import GitVfs


class TestDebianSource(testutils.DebianGitTestRepo):
    """Test L{gbp.deb.source}'s """

    def setUp(self):
        testutils.DebianGitTestRepo.setUp(self)
        context.chdir(self.repo.path)

    def test_is_native_file_3_file(self):
        """Test native package of format 3"""
        source = DebianSource('.')
        os.makedirs('debian/source')
        self.assertRaises(DebianSourceError,
                          source.is_native)

        dsf = DebianSourceFormat.from_content("3.0", "native")
        self.assertEqual(dsf.type, 'native')
        self.assertTrue(source.is_native())

        dsf = DebianSourceFormat.from_content("3.0", "quilt")
        self.assertEqual(dsf.type, 'quilt')
        self.assertFalse(source.is_native())

    def test_is_native_fallback_file(self):
        """Test native package without a debian/source/format file"""
        source = DebianSource('.')
        os.makedirs('debian/')
        self.assertRaises(DebianSourceError,
                          source.is_native)

        with open('debian/changelog', 'w') as f:
            f.write("""git-buildpackage (0.2.3) git-buildpackage; urgency=low

  * git doesn't like '~' in tag names so replace this with a dot when tagging

 -- Guido Guenther <agx@sigxcpu.org>  Mon,  2 Oct 2006 18:30:20 +0200
""")
        source = DebianSource('.')
        self.assertTrue(source.is_native())

    def _commit_format(self, version, format):
        # Commit a format file to disk
        if not os.path.exists('debian/source'):
            os.makedirs('debian/source')
        dsf = DebianSourceFormat.from_content(version, format)
        self.assertEqual(dsf.type, format)
        self.repo.add_files('.')
        self.repo.commit_all('foo')
        os.unlink('debian/source/format')
        self.assertFalse(os.path.exists('debian/source/format'))

    def test_is_native_file_3_git(self):
        """Test native package of format 3 from git"""
        self._commit_format('3.0', 'native')
        source = DebianSource(GitVfs(self.repo))
        self.assertTrue(source.is_native())

        self._commit_format('3.0', 'quilt')
        source = DebianSource(GitVfs(self.repo))
        self.assertFalse(source.is_native())
