# vim: set fileencoding=utf-8 :

"""Test L{Patch} class"""

from . import context  # noqa: 401

import os
import unittest

from gbp.patch_series import Patch


class TestPatch(unittest.TestCase):
    data_dir = os.path.splitext(__file__)[0] + '_data'

    def test_filename(self):
        """Get patch information from the filename"""
        p = Patch(os.path.join(self.data_dir, "doesnotexist.diff"))
        self.assertEqual('doesnotexist', p.subject)
        self.assertEqual({}, p.info)
        p = Patch(os.path.join(self.data_dir, "doesnotexist.patch"))
        self.assertEqual('doesnotexist', p.subject)
        p = Patch(os.path.join(self.data_dir, "doesnotexist"))
        self.assertEqual('doesnotexist', p.subject)
        self.assertEqual(None, p.author)
        self.assertEqual(None, p.email)
        self.assertEqual(None, p.date)

    def test_header(self):
        """Get the patch information from a patch header"""
        patchfile = os.path.join(self.data_dir, "patch1.diff")
        self.assertTrue(os.path.exists(patchfile))
        p = Patch(patchfile)
        self.assertEqual('This is patch1', p.subject)
        self.assertEqual("foo", p.author)
        self.assertEqual("foo@example.com", p.email)
        self.assertEqual("This is the long description.\n"
                         "It can span several lines.\n",
                         p.long_desc)
        self.assertEqual('Sat, 24 Dec 2011 12:05:53 +0100', p.date)
