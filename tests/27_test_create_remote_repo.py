# vim: set fileencoding=utf-8 :
# (C) 2016 Guido Günther <agx@sigxcpu.org>
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
"""Test the L{gbp} create_remote_repo command"""

import os
import unittest
import gbp.scripts.create_remote_repo as create_remote_repo


class TestGbpCreateRemoteRepoCommand(unittest.TestCase):
    def setUp(self):
        self.conffiles_save = os.environ.get('GBP_CONF_FILES')

    def tearDown(self):
        if self.conffiles_save:
            os.environ['GBP_CONF_FILES'] = self.conffiles_save

    def test_no_config_templates(self):
        self.confname = 'tests/data/gbp_nonexistent.conf'
        self.assertFalse(os.path.exists(self.confname))
        os.environ['GBP_CONF_FILES'] = self.confname

        _, _, sections = create_remote_repo.parse_args(['create-remote-repo'])
        self.assertEqual(create_remote_repo.get_config_names(sections),
                         [])

    def test_list_config_templates(self):
        self.confname = 'tests/data/gbp_create_remote_repo.conf'
        self.assertTrue(os.path.exists(self.confname))
        os.environ['GBP_CONF_FILES'] = self.confname

        _, _, sections = create_remote_repo.parse_args(['create-remote-repo'])
        self.assertEqual(create_remote_repo.get_config_names(sections),
                         ['config1', 'config2'])
