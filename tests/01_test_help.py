# vim: set fileencoding=utf-8 :
#
# check if --help works

import os
import unittest

class TestHelp(unittest.TestCase):

    def testhelp(self):
        for prog in [ "buildpackage", "import-orig", "import-dsc", "dch" ]:
            ret = os.system("./git-%s --help >/dev/null" % prog)
            self.assertEqual(ret, 0)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
