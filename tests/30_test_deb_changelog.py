# vim: set fileencoding=utf-8 :

"""
Test  L{gbp.deb.changelog.Changelog}

Test things here that don't fit nicely into the doctests that
also make up the API documentation.
"""

import unittest

from gbp.deb.changelog import ChangeLog


class TestQuoting(unittest.TestCase):
    def test_comma(self):
        """Test we properly parse maitainers with comma #737623"""
        changes = """git-buildpackage (0.9.2) unstable; urgency=low

  * List of changes

 -- Guido Günther, aftercomma <agx@sigxcpu.org>  Sun, 12 Nov 2017 19:00:00 +0200
"""
        cl = ChangeLog(changes)
        self.assertEquals(cl.author, 'Guido Günther, aftercomma')
        self.assertEquals(cl.email, 'agx@sigxcpu.org')
