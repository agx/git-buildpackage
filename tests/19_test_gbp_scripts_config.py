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
#    along with this program; if not, please see
#    <http://www.gnu.org/licenses/>
"""Test the L{gbp} config command"""

import os
import unittest
import gbp.scripts.config


class TestGbpConfigCommand(unittest.TestCase):
    class SingleValuePrintStub(object):
        def __init__(self):
            self.result = None

        def __call__(self, arg):
            self.result = arg

    class AllValuesPrintStub(object):
        def __init__(self, cmd):
            self.cmd = cmd
            self.result = {}

        def __call__(self, arg):
            k, v = arg.split('=', 1)
            self.result[k] = v

    def setUp(self):
        self.conffiles_save = os.environ.get('GBP_CONF_FILES')
        self.confname = 'tests/data/gbp_config.conf'
        self.assertTrue(os.stat(self.confname))
        os.environ['GBP_CONF_FILES'] = self.confname

    def test_invocation_single_value(self):
        """Can invoke it for a sngle value  without error"""
        ret = gbp.scripts.config.main(['doesnotmatter', 'config.color'])
        self.assertEqual(ret, 0)

    def test_invocation_missing_value(self):
        """Can we detect a missing value"""
        ret = gbp.scripts.config.main(['doesnotmatter', 'config.doesnotexist'])
        self.assertEqual(ret, 2)

    def test_print_cmd_single_value_default(self):
        """Can we fetch a single configuration value that is at it's default"""
        printstub = self.SingleValuePrintStub()
        query = 'config.color'
        ret = gbp.scripts.config.print_cmd_values(query, printstub)
        self.assertEqual(printstub.result, '%s=auto' % query)
        self.assertEqual(ret, 0)

    def test_print_cmd_single_value_empty_default(self):
        """Can we fetch a single configuration value that is at it's default which is empty"""
        printstub = self.SingleValuePrintStub()
        query = 'buildpackage.keyid'
        ret = gbp.scripts.config.print_cmd_values(query, printstub)
        self.assertEqual(printstub.result, '%s=' % query)
        self.assertEqual(ret, 0)

    def test_print_cmd_single_value_override(self):
        """Can we fetch a single configuration value that is overridden by config"""
        printstub = self.SingleValuePrintStub()
        query = 'config.color-scheme'
        ret = gbp.scripts.config.print_cmd_values(query, printstub)
        self.assertEqual(printstub.result, '%s=checkcheck' % query)
        self.assertEqual(ret, 0)

    def test_print_cmd_all_values(self):
        """Can we fetch the configuration for all commands"""
        for cmd in ['buildpackage',
                    'clone',
                    'config',
                    'create_remote_repo',
                    'dch',
                    'import_dsc',
                    'import_orig',
                    'pq',
                    'pull']:
            printstub = self.AllValuesPrintStub(cmd)
            ret = gbp.scripts.config.print_cmd_values(cmd, printstub)
            self.assertIn('%s.color' % cmd, printstub.result.keys())
            self.assertEquals(printstub.result['%s.color' % cmd], 'auto')
            self.assertEqual(ret, 0)

    def test_nonexistent_cmds(self):
        """Non-existing commands should print no values"""
        for cmd in ["import_dscs", "supercommand"]:
            printstub = self.AllValuesPrintStub(cmd)
            ret = gbp.scripts.config.print_cmd_values(cmd, printstub)
            self.assertEquals(printstub.result, dict())
            self.assertEqual(ret, 2)
