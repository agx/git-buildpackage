# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
"""provides some debian source package related helpers"""

import commands
import email
import os
import re
import shutil
import subprocess
import sys
import glob
import command_wrappers as gbpc
from errors import GbpError

# When trying to parse a version-number from a dsc or changes file, these are
# the valid characters.
debian_version_chars = 'a-zA-Z\d.~+-'

# compression types, extra options and extensions
compressor_opts = { 'gzip'  : [ '-n', 'gz' ],
                    'bzip2' : [ '', 'bz2' ],
                    'lzma'  : [ '', 'lzma' ],
                    'xz'    : [ '', 'xz' ] }

class NoChangelogError(Exception):
    """no changelog found"""
    pass

class ParseChangeLogError(Exception):
    """problem parsing changelog"""
    pass

class DscFile(object):
    """Keeps all needed data read from a dscfile"""
    compressions = r"(gz|bz2)"
    pkg_re = re.compile(r'Source:\s+(?P<pkg>.+)\s*')
    version_re = re.compile(r'Version:\s((?P<epoch>\d+)\:)?(?P<version>[%s]+)\s*$' % debian_version_chars)
    tar_re = re.compile(r'^\s\w+\s\d+\s+(?P<tar>[^_]+_[^_]+(\.orig)?\.tar\.%s)' % compressions)
    diff_re = re.compile(r'^\s\w+\s\d+\s+(?P<diff>[^_]+_[^_]+\.diff.(gz|bz2))')
    deb_tgz_re = re.compile(r'^\s\w+\s\d+\s+(?P<deb_tgz>[^_]+_[^_]+\.debian.tar.%s)' % compressions)
    format_re = re.compile(r'Format:\s+(?P<format>[0-9.]+)\s*')

    def __init__(self, dscfile):
        self.pkg = ""
        self.tgz = ""
        self.diff = ""
        self.deb_tgz = ""
        self.pkgformat = "1.0"
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
            m = self.deb_tgz_re.match(line)
            if m:
                self.deb_tgz = os.path.join(fromdir, m.group('deb_tgz'))
                continue
            m = self.tar_re.match(line)
            if m:
                self.tgz = os.path.join(fromdir, m.group('tar'))
                continue
            m = self.diff_re.match(line)
            if m:
                self.diff = os.path.join(fromdir, m.group('diff'))
                continue
            m = self.format_re.match(line)
            if m:
                self.pkgformat = m.group('format')
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


def orig_file(cp, compression):
    "The name of the orig.tar.gz belonging to changelog cp"
    ext = compressor_opts[compression][1]
    return "%s_%s.orig.tar.%s" % (cp['Source'], cp['Upstream-Version'], ext)


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

def has_orig(cp, compression, dir):
    "Check if orig.tar.gz exists in dir"
    try:
        os.stat( os.path.join(dir, orig_file(cp, compression)) )
    except OSError:
        return False
    return True

def symlink_orig(cp, compression, orig_dir, output_dir, force=False):
    """
    symlink orig.tar.gz from orig_dir to output_dir
    @return: True if link was created or src == dst
             False in case of error or src doesn't exist
    """
    orig_dir = os.path.abspath(orig_dir)
    output_dir = os.path.abspath(output_dir)

    if orig_dir == output_dir:
        return True

    src = os.path.join(orig_dir, orig_file(cp, compression))
    dst = os.path.join(output_dir, orig_file(cp, compression))
    if not os.access(src, os.F_OK):
        return False
    try:
        if os.access(dst, os.F_OK) and force:
            os.unlink(dst)
        os.symlink(src, dst)
    except OSError:
        return False
    return True

def do_uscan():
    p = subprocess.Popen(['uscan', '--dehs'], stdout=subprocess.PIPE)
    out = p.communicate()[0].split('\n')
    if "<status>up to date</status>" in out:
        # nothing to do.
        return (False, None)
    else:
        for row in out:
            if row.startswith('<messages>'):
                tarball = "../%s" % re.match(".*symlinked ([^\s]*) to it.*", row).group(1)
                break
        else:
            d = {}
            for row in out:
                for n in ('package', 'upstream-version', 'upstream-url'):
                    m = re.match("<%s>(.*)</%s>" % (n,n), row)
                    if m:
                        d[n] = m.group(1)
                    else:
                        continue
            d["ext"] = os.path.splitext(d['upstream-url'])[1]
            tarball = "../%(package)s_%(upstream-version)s.orig.tar%(ext)s" % d

            if not os.path.exists(tarball):
                return (True, None)
        return (True, tarball)

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

def repack_orig(archive, tmpdir, dest):
    """
    recreate a new .orig.tar.gz from tmpdir (useful when using filter option)
    """
    try:
        repackArchive = gbpc.RepackTarArchive(archive, tmpdir, dest)
        repackArchive()
    except gbpc.CommandExecFailed:
        print >>sys.stderr, "Failed to create %s" % archive
        raise GbpError
    return repackArchive.dir

def tar_toplevel(dir):
    """tar archives can contain a leading directory not"""
    unpacked = glob.glob('%s/*' % dir)
    unpacked.extend(glob.glob("%s/.*" % dir)) # include hidden files and folders
    # Check that dir contains nothing but a single folder:
    if len(unpacked) == 1 and os.path.isdir(unpacked[0]):
        return unpacked[0]
    else:
        return dir


def get_arch():
    pipe = subprocess.Popen(["dpkg", "--print-architecture"], shell=False, stdout=subprocess.PIPE)
    arch = pipe.stdout.readline().strip()
    return arch


def guess_upstream_version(archive, version_regex=r''):
    """
    guess the version from the filename of an upstgream archive
    @archive: filename to guess to version for
    @version_regex: additional version regex to apply, needs a 'version' group

    >>> guess_upstream_version('foo-bar_0.2.orig.tar.gz')
    '0.2'
    >>> guess_upstream_version('foo-Bar_0.2.orig.tar.gz')
    >>> guess_upstream_version('git-bar-0.2.tar.gz')
    '0.2'
    >>> guess_upstream_version('git-bar-0.2-rc1.tar.gz')
    '0.2-rc1'
    >>> guess_upstream_version('git-bar-0.2:~-rc1.tar.gz')
    '0.2:~-rc1'
    >>> guess_upstream_version('git-Bar-0A2d:rc1.tar.bz2')
    '0A2d:rc1'
    >>> guess_upstream_version('git-1.tar.bz2')
    '1'
    >>> guess_upstream_version('kvm_87+dfsg.orig.tar.gz')
    '87+dfsg'
    >>> guess_upstream_version('foo-Bar_0.2.orig.tar.gz')
    >>> guess_upstream_version('foo-Bar-a.b.tar.gz')
    """
    version_chars = r'[a-zA-Z\d\.\~\-\:\+]'
    extensions = r'\.tar\.(gz|bz2)'

    version_filters = map ( lambda x: x % (version_chars, extensions),
                       ( # Debian package_<version>.orig.tar.gz:
                         r'^[a-z\d\.\+\-]+_(?P<version>%s+)\.orig%s',
                         # Upstream package-<version>.tar.gz:
                         r'^[a-zA-Z\d\.\+\-]+-(?P<version>[0-9]%s*)%s'))
    if version_regex:
        version_filters = version_regex + version_filters
    for filter in version_filters:
        m = re.match(filter, os.path.basename(archive))
        if m:
            return m.group('version')

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
