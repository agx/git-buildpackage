# vim: set fileencoding=utf-8 :

"""Test L{Patch} class"""

from . import context  # noqa: 401

import os
import unittest

from gbp.patch_series import Patch, Dep3Patch


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


class TestDep3Patch(unittest.TestCase):
    data_dir = os.path.splitext(__file__)[0] + '_data'

    def test_encoding(self):
        """Make sure broken encoding does no affect import"""
        patchfile = os.path.join(self.data_dir, "dep3-iso8859-1.patch")
        self.assertTrue(os.path.exists(patchfile))
        p = Dep3Patch(patchfile)
        self.assertEqual(r'Replace all -- in man page by \-\- to make lintian happy.', p.subject)
        self.assertEqual("Roland Rosenfeld", p.author)
        self.assertEqual("roland@debian.org", p.email)
        self.assertEqual("", p.long_desc)

    def test_pseudo_headers(self):
        """Convert extra DEP-3 header into a git pseudo-header"""
        patchfile = os.path.join(self.data_dir, "dep3-longdesc-bug.patch")
        self.assertTrue(os.path.exists(patchfile))
        p = Dep3Patch(patchfile)
        self.assertEqual('Summary', p.subject)
        self.assertEqual("Ben Hutchings", p.author)
        self.assertEqual("ben@decadent.org.uk", p.email)
        self.assertEqual("""\
Bug: https://bugs.example.org/123456

Long description
""",
                         p.long_desc)


class TestMixedHeaderPatch(unittest.TestCase):
    data_dir = os.path.splitext(__file__)[0] + '_data'

    def test_mixed(self):
        """Get patch information from git mailimport and extra DEP-3 headers"""
        patchfile = os.path.join(self.data_dir, "usbip-fix-misuse-of-strncpy.patch")
        self.assertTrue(os.path.exists(patchfile))
        p = Dep3Patch(patchfile)
        self.assertEqual("usbip: Fix misuse of strncpy()", p.subject)
        self.assertEqual("Ben Hutchings", p.author)
        self.assertEqual("ben@decadent.org.uk", p.email)
        self.assertEqual("""\
Bug-Debian: https://bugs.debian.org/897802

gcc 8 reports:

usbip_device_driver.c: In function ‘read_usb_vudc_device’:
usbip_device_driver.c:106:2: error: ‘strncpy’ specified bound 256 equals destination size [-Werror=stringop-truncation]
  strncpy(dev->path, path, SYSFS_PATH_MAX);
  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
usbip_device_driver.c:125:2: error: ‘strncpy’ specified bound 32 equals destination size [-Werror=stringop-truncation]
  strncpy(dev->busid, name, SYSFS_BUS_ID_SIZE);
  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

I'm not convinced it makes sense to truncate the copied strings here,
but since we're already doing so let's ensure they're still null-
terminated.  We can't easily use strlcpy() here, so use snprintf().

usbip_common.c has the same problem.

Signed-off-by: Ben Hutchings <ben@decadent.org.uk>
""",
                         p.long_desc)


class TestBase64Patch(unittest.TestCase):
    data_dir = os.path.splitext(__file__)[0] + '_data'

    def test_parse(self):
        """Get patch information from git mailimport with base64 body but plain text patch"""
        patchfile = os.path.join(self.data_dir, "base64.patch")
        self.assertTrue(os.path.exists(patchfile))
        p = Dep3Patch(patchfile)
        self.assertEqual("Sort files in archive (reproducible builds)", p.subject)
        self.assertEqual("Nick Leverton", p.author)
        self.assertEqual("nick@leverton.org", p.email)
        self.assertEqual("""\
Sort files when using mergelib to create libnullmailer.a, to get
reproducible build

Author: Alexis Bienvenüe <pado@passoire.fr>
""",
                         p.long_desc)


class TestMarkerOnly(unittest.TestCase):
    data_dir = os.path.splitext(__file__)[0] + '_data'

    def test_parse(self):
        """Don't fail on empty patch header"""
        patchfile = os.path.join(self.data_dir, "916545.patch")
        self.assertTrue(os.path.exists(patchfile))
        p = Dep3Patch(patchfile)
        self.assertEqual("916545", p.subject)
