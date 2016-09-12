# vim: set fileencoding=utf-8 :

"""Test L{UpstreamSource}'s tarball unpack"""

from . import context

import os
import tarfile
import unittest

import six

import gbp.pkg


class TestUnpack(unittest.TestCase):
    """Make sure we unpack gzip and bzip2 archives correctly"""
    archive_prefix = "archive"

    def _unpack_dir(self, compression):
        return "%s-%s" % (self.archive_prefix, compression)

    def _check_files(self, files, comp):
        """Check if files exist in the unpacked dir"""
        for f in files:
            target = os.path.join(self._unpack_dir(comp), f)
            assert os.path.exists(target), "%s does not exist" % target

    def _create_archive(self, comp):
        filelist = ['README.md', 'setup.py']

        name = "%s_0.1.tar.%s" % (self.archive_prefix, comp)
        t = tarfile.open(name=name, mode='w:%s' % comp)
        for f in filelist:
            t.add(os.path.join(self.top, f),
                  os.path.join(self._unpack_dir(comp), f))
        t.close()
        return name, filelist

    def setUp(self):
        self.dir = context.new_tmpdir(__name__)
        self.top = context.projectdir
        context.chdir(self.dir)
        self.archives = {}
        for ext in ["gz", "bz2"]:
            self.archives[ext] = self._create_archive(ext)

    def tearDown(self):
        context.teardown()

    def test_upstream_source_type(self):
        for (comp, archive) in six.iteritems(self.archives):
            source = gbp.pkg.UpstreamSource(archive[0])
            assert source.is_orig() is True
            assert source.is_dir() is False
            assert source.unpacked is None
            source.unpack(".")
            assert source.is_orig() is True
            assert source.is_dir() is False
            assert type(source.unpacked) == str

    def test_upstream_source_unpack(self):
        for (comp, archive) in six.iteritems(self.archives):
            source = gbp.pkg.UpstreamSource(archive[0])
            source.unpack(".")
            self._check_files(archive[1], comp)

    def test_upstream_source_unpack_no_filter(self):
        for (comp, archive) in six.iteritems(self.archives):
            source = gbp.pkg.UpstreamSource(archive[0])
            source.unpack(".", [])
            self._check_files(archive[1], comp)

    def test_upstream_source_unpack_filtered(self):
        exclude = "README.md"

        for (comp, archive) in six.iteritems(self.archives):
            source = gbp.pkg.UpstreamSource(archive[0])
            source.unpack(".", [exclude])
            archive[1].remove(exclude)
            self._check_files(archive[1], comp)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
