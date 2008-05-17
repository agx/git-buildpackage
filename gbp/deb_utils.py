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
    version_re = re.compile("Version:\s(\d+\:)?(?P<version>[%s]+)\s*$" % debian_version_chars)
    tar_re = re.compile('^\s\w+\s\d+\s+(?P<tar>[^_]+_[^_]+(\.orig)?\.tar\.(gz|bz2))')
    diff_re = re.compile('^\s\w+\s\d+\s+(?P<diff>[^_]+_[^_]+\.diff.(gz|bz2))')

    def __init__(self, dscfile):
        self.pkg = ""
        self.tgz = ""
        self.diff = ""
        self.dscfile = os.path.abspath(dscfile)
        f = file(self.dscfile)
        fromdir = os.path.dirname(os.path.abspath(dscfile))
        for line in f:
            m = self.version_re.match(line)
            if m:
                if '-' in m.group('version'):
                    self.debian_version = m.group('version').split("-")[-1]
                    self.upstream_version = "-".join(m.group('version').split("-")[0:-1])
                    self.native = False
                else:
                    self.native = True # Debian native package
                    self.upstream_version = m.group('version')
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
            raise GbpError, "Cannot parse package name from %s" % self.dscfile
        elif not self.tgz:
            raise GbpError, "Cannot parse archive name from %s" % self.dscfile


def parse_dsc(dscfile):
    """parse dsc by creating a DscFile object"""
    try:
        dsc = DscFile(dscfile)
    except IOError, err:
        raise GbpError, "Error reading dsc file: %s" % err
    else:
        try:
            if dsc.native:
                print "Debian Native Package"
                print "Version:", dsc.upstream_version
            else:
                print "Upstream version:", dsc.upstream_version
                print "Debian version:", dsc.debian_version
        except AttributeError:
            raise GbpError, "Error parsing dsc file %s" % dscfile
    return dsc


def parse_changelog(changelog):
    """parse changelog file changelog"""
    if not os.access(changelog, os.F_OK):
        raise NoChangelogError, "Changelog %s not found" % (changelog, )
    status, output = commands.getstatusoutput('dpkg-parsechangelog -l%s' % (changelog, ))
    if status:
        raise ParseChangeLogError, output
    cp = email.message_from_string(output)
    if '-' in cp['Version']:
        upstream_version, cp['Debian-Version'] = cp['Version'].rsplit('-', 1)
        if ':' in upstream_version:
            cp['Epoch'], cp['Upstream-Version'] = upstream_version.split(':', 1)
        else:
            cp['Upstream-Version'] = upstream_version
    else:
        cp['Debian-Version'] = cp['Version']
    return cp
 

def orig_file(cp):
    "The name of the orig.tar.gz belonging to changelog cp"
    return "%s_%s.orig.tar.gz" % (cp['Source'], cp['Upstream-Version'])


def is_native(cp):
    "Is this a debian native package"
    return [ True, False ]['-' in cp['Version']]


def has_orig(cp, dir):
    "Check if orig.tar.gz exists in dir"
    try:
        os.stat( os.path.join(dir, orig_file(cp)) )
    except OSError:
        return False
    return True

def copy_orig(cp, orig_dir, output_dir):
    """copy orig.tar.gz from orig_dir to output_dir"""
    orig_dir = os.path.abspath(orig_dir)
    output_dir = os.path.abspath(output_dir)

    if orig_dir == output_dir:
        return True

    try:
        shutil.copyfile(os.path.join(orig_dir, orig_file(cp)),
            os.path.join(output_dir, orig_file(cp)))
    except IOError:
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


def _test():
    import doctest
    doctest.testmod()

if __name__ == '__main__':
    _test()

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
