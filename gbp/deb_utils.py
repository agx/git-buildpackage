# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
"""provides some debian source package related helpers"""

import commands
import email
import os
import re
import shutil
import sys
import glob
import command_wrappers as gbpc
from errors import GbpError

# When trying to parse a version-number from a dsc or changes file, these are
# the valid characters.
debian_version_chars = 'a-zA-Z\d.~+-'

class NoChangelogError(Exception):
    """no changelog found"""
    pass

class ParseChangeLogError(Exception):
    """problem parsing changelog"""
    pass


class DscFile(object):
    """Keeps all needed data read from a dscfile"""
    pkg_re = re.compile('Source:\s+(?P<pkg>.+)\s*')
    version_re = re.compile("Version:\s((?P<epoch>\d+)\:)?(?P<version>[%s]+)\s*$" % debian_version_chars)
    tar_re = re.compile('^\s\w+\s\d+\s+(?P<tar>[^_]+_[^_]+(\.orig)?\.tar\.(gz|bz2))')
    diff_re = re.compile('^\s\w+\s\d+\s+(?P<diff>[^_]+_[^_]+\.diff.(gz|bz2))')

    def __init__(self, dscfile):
        self.pkg = ""
        self.tgz = ""
        self.diff = ""
        self.debian_version = ""
        self.upstream_version = ""
        self.native = False
        self.dscfile = os.path.abspath(dscfile)

        f = file(self.dscfile)
        fromdir = os.path.dirname(os.path.abspath(dscfile))
        for line in f:
            m = self.version_re.match(line)
            if m and not self.upstream_version:
                if '-' in m.group('version'):
                    self.debian_version = m.group('version').split("-")[-1]
                    self.upstream_version = "-".join(m.group('version').split("-")[0:-1])
                    self.native = False
                else:
                    self.native = True # Debian native package
                    self.upstream_version = m.group('version')
                if m.group('epoch'):
                    self.epoch = m.group('epoch')
                else:
                    self.epoch = ""
                continue
            m = self.pkg_re.match(line)
            if m:
                self.pkg = m.group('pkg')
                continue
            m = self.tar_re.match(line)
            if m:
                self.tgz = os.path.join(fromdir, m.group('tar'))
                continue
            m = self.diff_re.match(line)
            if m:
                self.diff = os.path.join(fromdir, m.group('diff'))
                continue
        f.close()

        if not self.pkg:
            raise GbpError, "Cannot parse package name from '%s'" % self.dscfile
        elif not self.tgz:
            raise GbpError, "Cannot parse archive name from '%s'" % self.dscfile
        if not self.upstream_version:
            raise GbpError, "Cannot parse version number from '%s'" % self.dscfile
        if not self.native and not self.debian_version:
            raise GbpError, "Cannot parse Debian version number from '%s'" % self.dscfile

    def _get_version(self):
        version = [ "", self.epoch + ":" ][len(self.epoch) > 0]
        if self.native:
            version += self.upstream_version
        else:
            version += "%s-%s" % (self.upstream_version, self.debian_version)
        return version

    version = property(_get_version)

    def __str__(self):
        return "<%s object %s>" % (self.__class__.__name__, self.dscfile)


def parse_dsc(dscfile):
    """parse dsc by creating a DscFile object"""
    try:
        dsc = DscFile(dscfile)
    except IOError, err:
        raise GbpError, "Error reading dsc file: %s" % err

    return dsc


def parse_changelog(changelog):
    """
    parse changelog file changelog

    cp['Version']: full version string including epoch
    cp['Upstream-Version']: upstream version, if not debian native
    cp['Debian-Version']: debian release
    cp['Epoch']: epoch, if any
    cp['NoEpoch-Version']: full version string excluding epoch
    """
    if not os.access(changelog, os.F_OK):
        raise NoChangelogError, "Changelog %s not found" % (changelog, )
    status, output = commands.getstatusoutput('dpkg-parsechangelog -l%s' % (changelog, ))
    if status:
        raise ParseChangeLogError, output
    cp = email.message_from_string(output)
    try:
        if ':' in cp['Version']:
            cp['Epoch'], cp['NoEpoch-Version'] = cp['Version'].split(':', 1)
        else:
            cp['NoEpoch-Version'] = cp['Version']
        if '-' in cp['NoEpoch-Version']:
            cp['Upstream-Version'], cp['Debian-Version'] = cp['NoEpoch-Version'].rsplit('-', 1)
        else:
            cp['Debian-Version'] = cp['NoEpoch-Version']
    except TypeError:
        raise ParseChangeLogError, output.split('\n')[0]
    return cp
 

def orig_file(cp):
    "The name of the orig.tar.gz belonging to changelog cp"
    return "%s_%s.orig.tar.gz" % (cp['Source'], cp['Upstream-Version'])


def is_native(cp):
    "Is this a debian native package"
    return [ True, False ]['-' in cp['Version']]


def has_epoch(cp):
    """does the topmost version number contain an epoch"""
    try:
        if cp['Epoch']:
            return True
    except KeyError:
        return False

def has_orig(cp, dir):
    "Check if orig.tar.gz exists in dir"
    try:
        os.stat( os.path.join(dir, orig_file(cp)) )
    except OSError:
        return False
    return True

def symlink_orig(cp, orig_dir, output_dir, force=False):
    """
    symlink orig.tar.gz from orig_dir to output_dir
    @return: True if link was created or src == dst
             False in case of error or src doesn't exist
    """
    orig_dir = os.path.abspath(orig_dir)
    output_dir = os.path.abspath(output_dir)

    if orig_dir == output_dir:
        return True

    src = os.path.join(orig_dir, orig_file(cp))
    dst = os.path.join(output_dir, orig_file(cp))
    if not os.access(src, os.F_OK):
        return False
    try:
        if os.access(dst, os.F_OK) and force:
            os.unlink(dst)
        os.symlink(src, dst)
    except OSError:
        return False
    return True

def unpack_orig(archive, tmpdir, filters):
    """
    unpack a .orig.tar.gz to tmpdir, leave the cleanup to the caller in case of
    an error
    """
    try:
        unpackArchive = gbpc.UnpackTarArchive(archive, tmpdir, filters)
        unpackArchive()
    except gbpc.CommandExecFailed:
        print >>sys.stderr, "Unpacking of %s failed" % archive
        raise GbpError
    return unpackArchive.dir


def tar_toplevel(dir):
    """tar archives can contain a leading directory not"""
    unpacked = glob.glob('%s/*' % dir)
    if len(unpacked) == 1:
        return unpacked[0]
    else:
        return dir


def _test():
    import doctest
    doctest.testmod()

if __name__ == '__main__':
    _test()

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
