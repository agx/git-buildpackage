# vim: set fileencoding=utf-8 :

import glob
import os
import shutil
import tarfile
import tempfile

import gbp.deb

class TestUnpack:
    """Make sure we unpack gzip and bzip2 archives correctly"""
    def _createArchive(self, comp):
        archive = "archive"
        name = "%s_0.1.tar.%s" % (archive, comp)
        t = tarfile.open(name= name, mode='w:%s' % comp)
        for f in glob.glob(os.path.join(self.top, "*.py")):
            t.add(os.path.join(self.top,f),
                  os.path.join("%s-%s" % (archive, comp),
                               os.path.basename(f)))
        t.close()
        return name

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='gbp_%s_' % __name__, dir='.')
        self.top = os.path.abspath(os.curdir)
        os.chdir(self.dir)
        self.archives = {}
        for ext in [ "gz", "bz2" ]:
            self.archives[ext] = self._createArchive(ext)

    def tearDown(self):
        os.chdir(self.top)
        if not os.getenv("GBP_TESTS_NOCLEAN"):
            shutil.rmtree(self.dir)

    def testUnpack(self):
        for (comp, archive) in self.archives.iteritems():
            gbp.deb.unpack_orig(archive, ".", [])

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
