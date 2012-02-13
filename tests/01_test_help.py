# vim: set fileencoding=utf-8 :

"""Check if --help works"""

import os
import unittest

class TestHelp(unittest.TestCase):
    """Test help output of gbp commands"""
    os.environ['PYTHONPATH'] = '.'

    def testHelp(self):
        for prog in [ "buildpackage", "import-orig", "import-dsc", "dch" ]:
            ret = os.system("bin/git-%s --help >/dev/null" % prog)
            self.assertEqual(ret, 0)

    def testHelpGbp(self):
        for prog in [ "pull", "clone", "pq", "create-remote-repo" ]:
            ret = os.system("bin/gbp-%s --help >/dev/null" % prog)
            self.assertEqual(ret, 0)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
