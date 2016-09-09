# vim: set fileencoding=utf-8 :

"""Test the L{UpstreamSource} class"""

from . import context

import glob
import os
import tarfile
import unittest
import zipfile

from gbp.pkg import UpstreamSource


class TestDir(unittest.TestCase):
    def setUp(self):
        self.tmpdir = context.new_tmpdir(__name__)
        self.upstream_dir = self.tmpdir.join('test-1.0')
        os.mkdir(self.upstream_dir)

    def test_directory(self):
        """Upstream source is a directory"""
        source = UpstreamSource(self.upstream_dir)
        self.assertEqual(source.is_orig(), False)
        self.assertEqual(source.path, self.upstream_dir)
        self.assertEqual(source.unpacked, self.upstream_dir)
        self.assertEqual(source.guess_version(), ('test', '1.0'))

    def tearDown(self):
        context.teardown()


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
        self.tmpdir = context.new_tmpdir(__name__)
        self.source = UpstreamSource(os.path.join(context.projectdir, "gbp"))

    def tearDown(self):
        context.teardown()

    def test_pack_tar(self):
        """Check if packing tar archives works"""
        target = self.tmpdir.join("gbp_0.1.tar.bz2")
        repacked = self.source.pack(target)
        self.assertEqual(repacked.is_orig(), True)
        self.assertEqual(repacked.is_dir(), False)
        self.assertEqual(repacked.guess_version(), ('gbp', '0.1'))
        self._check_tar(repacked, ["gbp/errors.py", "gbp/__init__.py"])

    def test_pack_filtered(self):
        """Check if filtering out files works"""
        target = self.tmpdir.join("gbp_0.1.tar.bz2")
        repacked = self.source.pack(target, ["__init__.py"])
        self.assertEqual(repacked.is_orig(), True)
        self.assertEqual(repacked.is_dir(), False)
        self._check_tar(repacked, ["gbp/errors.py"],
                                  ["gbp/__init__.py"])


class TestZip(unittest.TestCase):
    """Test if unpacking zip archives works"""
    def setUp(self):
        self.tmpdir = context.new_tmpdir(__name__)
        self.zipfile = self.tmpdir.join("gbp-0.1.zip")
        z = zipfile.ZipFile(self.zipfile, "w")
        for f in glob.glob(os.path.join(context.projectdir, "gbp/*.py")):
            z.write(f, f, zipfile.ZIP_DEFLATED)
        z.close()

    def tearDown(self):
        context.teardown()

    def test_unpack(self):
        source = UpstreamSource(self.zipfile)
        self.assertEqual(source.is_orig(), False)
        self.assertEqual(source.is_dir(), False)
        self.assertEqual(source.unpacked, None)
        self.assertEqual(source.guess_version(), ('gbp', '0.1'))
        source.unpack(str(self.tmpdir))
        self.assertNotEqual(source.unpacked, None)
