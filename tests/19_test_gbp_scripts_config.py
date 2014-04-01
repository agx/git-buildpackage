# vim: set fileencoding=utf-8 :
# (C) 2014 Guido Günther <agx@sigxcpu.org>
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
"""Test L{gbp} config"""

import os
import sys
import unittest
import gbp.scripts.config

class TestGbpConfigCommand(unittest.TestCase):

    def setUp(self):
        self.conffiles_save = os.environ.get('GBP_CONF_FILES')
        self.confname = 'tests/data/gbp_config.conf'
        self.assertTrue(os.stat(self.confname))
        os.environ['GBP_CONF_FILES'] = self.confname

    def test_invocation_single_value(self):
        """Test if we an invoke it without error"""
        ret = gbp.scripts.config.main(['doesnotmatter', 'coolcommand.branchname'])
        self.assertEqual(ret, 0)

    def test_invocation_missing_value(self):
        """Test if we an invoke it without error"""
        ret = gbp.scripts.config.main(['doesnotmatter', 'coolcommand.doesnotexist'])
        self.assertEqual(ret, 1)

    def test_invocation_parse_error(self):
        """Test if we an invoke it without error"""
        ret = gbp.scripts.config.main(['doesnotmatter', 'mustcontaindot'])
        self.assertEqual(ret, 2)

    def test_print_single_value(self):
        class Printstub(object):
            result = None
            def __call__(self, arg):
                self.result = arg

        printstub = Printstub()
        ret = gbp.scripts.config.print_single_value('coolcommand.branchname', printstub)
        self.assertEqual(printstub.result, 'abranch')
        self.assertEqual(ret, 0)

