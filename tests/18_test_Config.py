# vim: set fileencoding=utf-8 :

import os
import unittest
from gbp.config import GbpOptionParser
from . import context

class TestConfigParser(unittest.TestCase):
    def setUp(self):
        self.conffiles_save = os.environ.get('GBP_CONF_FILES')
        self.confname = 'tests/data/test1.conf'
        self.assertTrue(os.stat(self.confname))
        os.environ['GBP_CONF_FILES'] = self.confname

    def tearDown(self):
        if self.conffiles_save:
            os.environ['GBP_CONF_FILES'] = self.conffiles_save

    def test_default(self):
        """
        A value only in the default section should be available in all commands
        """
        for n in range(1,5):
            for prefix in [ '', 'git-', 'gbp-' ]:
                parser = GbpOptionParser('cmd%d' % n)
                self.assertEqual(parser.config['default_option'], 'default_default1')

    def test_single_override(self):
        """
        A value in any command section should override the default
        """
        for prefix in [ '', 'git-', 'gbp-' ]:
            parser = GbpOptionParser('%scmd1' % prefix)
            self.assertEqual(parser.config['single_override_option1'], 'single_override_value1')

    def test_single_git_override(self):
        """
        A value in any git-command section should override the default
        """
        for prefix in [ '', 'git-' ]:
            parser = GbpOptionParser('%scmd2' % prefix)
            self.assertEqual(parser.config['single_git_override_option1'], 'single_git_override_value1')

    def test_single_gbp_override(self):
        """
        A value in any gbp-command section should override the default
        """
        for prefix in [ '', 'gbp-' ]:
            parser = GbpOptionParser('%scmd3' % prefix)
            self.assertEqual(parser.config['single_gbp_override_option1'], 'single_gbp_override_value1')
        # FIXME: for all prefixes

    def test_new_overrides_git(self):
        """
        A value in the cmd section should override the old git-cmd section independent from
        how we're invoked
        """
        for n in range(4, 6):
            for prefix in [ '', 'git-']:
                cmd = '%scmd%d' % (prefix, n)
                parser = GbpOptionParser(cmd)
                actual = parser.config['new_overrides_git_option1']
                expected = 'new_overrides_git_value1'
                self.assertEqual(actual, expected, "%s != %s for %s" % (actual, expected, cmd))
