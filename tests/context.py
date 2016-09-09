# this context.py should be included by all tests
# idea from http://kennethreitz.com/repository-structure-and-python.html

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.abspath('..'))

import gbp       # noqa: E402
import gbp.log   # noqa: E402

gbp.log.setup(False, False)


# the top or root dir of the git-buildpackage source tree to be used by tests
projectdir = os.path.dirname(os.path.dirname(os.path.abspath(gbp.__file__)))

_chdir_backup = None
_tmpdirs = []


def chdir(dir):
    global _chdir_backup
    if not _chdir_backup:
        _chdir_backup = os.path.abspath(os.curdir)
    os.chdir(str(dir))


def new_tmpdir(name):
    global _tmpdirs
    prefix = 'gbp_%s_' % name
    tmpdir = TmpDir(prefix)
    _tmpdirs.append(tmpdir)
    return tmpdir


def teardown():
    if _chdir_backup:
        os.chdir(_chdir_backup)
    for tmpdir in _tmpdirs:
        tmpdir.rmdir()
    del _tmpdirs[:]


class TmpDir(object):

    def __init__(self, suffix='', prefix='tmp'):
        self.path = tempfile.mkdtemp(suffix=suffix, prefix=prefix)

    def rmdir(self):
        if self.path and not os.getenv("GBP_TESTS_NOCLEAN"):
            shutil.rmtree(self.path)
            self.path = None

    def __repr__(self):
        return self.path

    def join(self, *args):
        return os.path.join(self.path, *args)
