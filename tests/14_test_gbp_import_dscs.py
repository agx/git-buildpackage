# vim: set fileencoding=utf-8 :
# (C) 2012 Guido Günther <agx@sigxcpu.org>
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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Test L{gbp.pq}"""

import os
import testutils
import gbp.scripts.import_dscs as import_dscs


class StubGitImportDsc(object):
    """
    A Stub for GitImportDsc.
    """
    def __init__(self, args):
        self.failfile = None
        for arg in args:
            if arg.startswith('--failfile'):
                self.failfile = "%s.dsc" % arg.split('=')[1]

    def importdsc(self, dsc):
        """
        Stub the dsc import and fail if we were told to do
        so by the --failfile option.
        """
        return 1 if dsc.filename == self.failfile else 0

class DscStub(object):
    def __init__(self, filename, version):
        self.filename = filename
        self.version = version

def stub_parse_dsc(filename):
    # filename is like file1.dsc, file2.dsc, use
    # the digit as version number
    version = filename[4]
    return DscStub(filename, version)


# hook up stubs
import_dscs.GitImportDsc = StubGitImportDsc
import_dscs.parse_dsc = stub_parse_dsc


class TestImportDscs(testutils.DebianGitTestRepo):
    """Test L{gbp.scripts.import_dscs}'s """

    def setUp(self):
        self.toplevel = os.getcwd()
        testutils.DebianGitTestRepo.setUp(self)
        os.chdir(self.repo.path)

    def test_import_success(self):
        """Test importing success with stub"""
        ret = import_dscs.main(['argv0', 'file1.dsc', 'file2.dsc'])
        self.assertEqual(ret, 0)

    def test_import_fail_first(self):
        ret = import_dscs.main(['argv0',
                                '--failfile=file1',
                                'file1.dsc'])
        self.assertEqual(ret, 1)

    def test_import_fail_second(self):
        ret = import_dscs.main(['argv0',
                                '--failfile=file1',
                                '--failfile=file2',
                                'file1.dsc',
                                'file2.dsc'])
        self.assertEqual(ret, 1)

    def tearDown(self):
        testutils.DebianGitTestRepo.tearDown(self)
        os.chdir(self.toplevel)

