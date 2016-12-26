# vim: set fileencoding=utf-8 :

from .. import context  # noqa: F401

import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

import gbp.log
import gbp.errors
from gbp.deb.changelog import ChangeLog

from . gbplogtester import GbpLogTester
from . debiangittestrepo import DebianGitTestRepo
from . capture import capture_stdout, capture_stderr

__all__ = ['GbpLogTester', 'DebianGitTestRepo', 'OsReleaseFile',
           'MockedChangeLog', 'get_dch_default_urgency',
           'capture_stderr', 'capture_stdout',
           'ls_dir', 'ls_tar', 'ls_zip']


class OsReleaseFile(object):
    """Repesents a simple file with key-value pairs"""

    def __init__(self, filename):
        self._values = {}

        try:
            with open(filename, 'r') as filed:
                for line in filed.readlines():
                    try:
                        key, value = line.split('=', 1)
                    except ValueError:
                        pass
                    else:
                        self._values[key] = value.strip()
        except IOError as err:
            gbp.log.info('Failed to read OS release file %s: %s' %
                         (filename, err))

    def __getitem__(self, key):
        if key in self._values:
            return self._values[key]
        return None

    def __contains__(self, key):
        return key in self._values

    def __str__(self):
        return str(self._values)

    def __repr__(self):
        return repr(self._values)


class MockedChangeLog(ChangeLog):
    contents = """foo (%s) experimental; urgency=low

  %s

 -- Debian Maintainer <maint@debian.org>  Sat, 01 Jan 2012 00:00:00 +0100"""

    def __init__(self, version, changes="a important change"):
        ChangeLog.__init__(self,
                           contents=self.contents % (version, changes))


def get_dch_default_urgency():
    """Determine the default urgency level used by dch"""
    urgency = 'medium'
    tempdir = tempfile.mkdtemp()
    tmp_dch_name = os.path.join(tempdir, 'changelog')
    try:
        dch_cmd = ['debchange', '--create', '--empty', '--changelog', tmp_dch_name,
                   '--package=foo', '--newversion=1',
                   '--distribution=UNRELEASED']
        ret = subprocess.Popen(dch_cmd).wait()
    except OSError:
        pass
    else:
        if ret == 0:
            with open(tmp_dch_name) as dchfile:
                header = dchfile.readline().strip()
                urgency = header.split()[-1].replace('urgency=', '')
    finally:
        if os.path.isdir(tempdir):
            shutil.rmtree(tempdir)
    return urgency


def ls_dir(directory, directories=True):
    """List the contents of directory, recurse to subdirectories"""
    contents = set()
    for root, dirs, files in os.walk(directory):
        prefix = ''
        if root != directory:
            prefix = os.path.relpath(root, directory) + '/'
        contents.update(['%s%s' % (prefix, fname) for fname in files])
        if directories:
            contents.update(['%s%s' % (prefix, dname) for dname in dirs])
    return contents


def ls_tar(tarball, directories=True):
    """List the contents of tar archive"""
    tmpdir = tempfile.mkdtemp()
    try:
        tarobj = tarfile.open(tarball, 'r')
        tarobj.extractall(tmpdir)
        return ls_dir(tmpdir, directories)
    finally:
        shutil.rmtree(tmpdir)


def ls_zip(archive, directories=True):
    """List the contents of zip file"""
    tmpdir = tempfile.mkdtemp()
    try:
        zipobj = zipfile.ZipFile(archive, 'r')
        zipobj.extractall(tmpdir)
        return ls_dir(tmpdir, directories)
    finally:
        shutil.rmtree(tmpdir)
