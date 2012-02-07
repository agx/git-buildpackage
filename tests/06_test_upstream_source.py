# vim: set fileencoding=utf-8 :

"""Test the L{UpstreamSource} class"""

import glob
import os
import shutil
import tarfile
import tempfile
import unittest
import zipfile

from gbp.deb import UpstreamSource

class TestDir(unittest.TestCase):
    def test_directory(self):
        """Upstream source is a directory"""
        source = UpstreamSource('.')
        self.assertEqual(source.is_orig(), False)
        self.assertEqual(source.path, '.')
        self.assertEqual(source.unpacked, '.')


class TestTar(unittest.TestCase):
    """Test if packing tar archives works"""
    def _check_tar(self, us, positive=[], negative=[]):
        t = tarfile.open(name=us.path, mode="r:bz2")
        for f in positive:
            i = t.getmember(f)
            self.assertEqual(type(i), tarfile.TarInfo)

        for f in negative:
            try:
                t.getmember(f)
                self.fail("Found %s in archive" % f)
            except KeyError:
                pass
        t.close()

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='gbp_%s_' % __name__, dir='.')

    def tearDown(self):
        if not os.getenv("GBP_TESTS_NOCLEAN"):
            shutil.rmtree(self.tmpdir)

    def test_pack_tar(self):
        """Check if packing tar archives works"""
        source = UpstreamSource(os.path.abspath("gbp/"))
        target = os.path.join(self.tmpdir,
                     "gbp_0.1.tar.bz2")
        repacked = source.pack(target)
        self.assertEqual(repacked.is_orig(), True)
        self.assertEqual(repacked.is_dir(), False)
        self._check_tar(repacked, ["gbp/errors.py", "gbp/__init__.py"])

    def test_pack_filtered(self):
        """Check if filtering out files works"""
        source = UpstreamSource(os.path.abspath("gbp/"))
        target = os.path.join(self.tmpdir,
                     "gbp_0.1.tar.bz2")
        repacked = source.pack(target, ["__init__.py"])
        self.assertEqual(repacked.is_orig(), True)
        self.assertEqual(repacked.is_dir(), False)
        self._check_tar(repacked, ["gbp/errors.py"],
                                  ["gbp/__init__.py"])


class TestZip(unittest.TestCase):
    """Test if unpacking zip archives works"""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='gbp_%s_' % __name__, dir='.')
        self.zipfile = os.path.join(self.tmpdir, "gbp-0.1.zip")
        z = zipfile.ZipFile(os.path.join(self.tmpdir, "gbp-0.1.zip"), "w")
        for f in glob.glob("gbp/*.py"):
            z.write(f, f, zipfile.ZIP_DEFLATED)
        z.close()

    def tearDown(self):
        if not os.getenv("GBP_TESTS_NOCLEAN"):
            shutil.rmtree(self.tmpdir)

    def test_unpack(self):
        source = UpstreamSource(self.zipfile)
        self.assertEqual(source.is_orig(), False)
        self.assertEqual(source.is_dir(), False)
        self.assertEqual(source.unpacked, None)
        source.unpack(self.tmpdir)
        self.assertNotEqual(source.unpacked, None)

