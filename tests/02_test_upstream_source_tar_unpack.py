# vim: set fileencoding=utf-8 :

"""Test L{UpstreamSource}'s tarball unpack"""

import os
import shutil
import tarfile
import tempfile

import gbp.deb

class TestUnpack:
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
        filelist = [ 'README', 'setup.py' ]

        name = "%s_0.1.tar.%s" % (self.archive_prefix, comp)
        t = tarfile.open(name= name, mode='w:%s' % comp)
        for f in filelist:
            t.add(os.path.join(self.top, f),
                  os.path.join(self._unpack_dir(comp), f))
        t.close()
        return name, filelist

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='gbp_%s_' % __name__, dir='.')
        self.top = os.path.abspath(os.curdir)
        os.chdir(self.dir)
        self.archives = {}
        for ext in [ "gz", "bz2" ]:
            self.archives[ext] = self._create_archive(ext)

    def tearDown(self):
        os.chdir(self.top)
        if not os.getenv("GBP_TESTS_NOCLEAN"):
            shutil.rmtree(self.dir)

    def test_upstream_source_type(self):
        for (comp, archive) in self.archives.iteritems():
            source = gbp.pkg.UpstreamSource(archive[0])
            assert source.is_orig() == True
            assert source.is_dir() == False
            assert source.unpacked == None
            source.unpack(".")
            assert source.is_orig() == True
            assert source.is_dir() == False
            assert type(source.unpacked) == str

    def test_upstream_source_unpack(self):
        for (comp, archive) in self.archives.iteritems():
            source = gbp.pkg.UpstreamSource(archive[0])
            source.unpack(".")
            self._check_files(archive[1], comp)

    def test_upstream_source_unpack_no_filter(self):
        for (comp, archive) in self.archives.iteritems():
            source = gbp.pkg.UpstreamSource(archive[0])
            source.unpack(".", [])
            self._check_files(archive[1], comp)

    def test_upstream_source_unpack_filtered(self):
        exclude = "README"

        for (comp, archive) in self.archives.iteritems():
            source = gbp.pkg.UpstreamSource(archive[0])
            source.unpack(".", [exclude])
            archive[1].remove(exclude)
            self._check_files(archive[1], comp)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
