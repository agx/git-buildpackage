# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
"""provides some debian source package related helpers"""

import commands
import email
import os
import re
import subprocess
import sys
import glob
import command_wrappers as gbpc
from errors import GbpError
from gbp.git import GitRepositoryError

# When trying to parse a version-number from a dsc or changes file, these are
# the valid characters.
debian_version_chars = 'a-zA-Z\d.~+-'

# Valid package names according to Debian Policy Manual 5.6.1:
# "Package names (both source and binary, see Package, Section 5.6.7)
# must consist only of lower case letters (a-z), digits (0-9), plus (+)
# and minus (-) signs, and periods (.). They must be at least two
# characters long and must start with an alphanumeric character."
packagename_re = re.compile("^[a-z0-9][a-z0-9\.\+\-]+$")
packagename_msg = """Package names must be at least two characters long, start with an
alphanumeric and can only containg lower case letters (a-z), digits
(0-9), plus signs (+), minus signs (-), and periods (.)"""

# Valid upstream versions according to Debian Policy Manual 5.6.12:
# "The upstream_version may contain only alphanumerics[32] and the
# characters . + - : ~ (full stop, plus, hyphen, colon, tilde) and
# should start with a digit. If there is no debian_revision then hyphens
# are not allowed; if there is no epoch then colons are not allowed."
# Since we don't know about any epochs and debian revisions yet, the
# last two conditions are not checked.
upstreamversion_re = re.compile("^[0-9][a-z0-9\.\+\-\:\~]*$")
upstreamversion_msg = """Upstream version numbers must start with a digit and can only containg lower case
letters (a-z), digits (0-9), full stops (.), plus signs (+), minus signs
(-), colons (:) and tildes (~)"""

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


class DpkgCompareVersions(gbpc.Command):
    cmd='/usr/bin/dpkg'

    def __init__(self):
        if not os.access(self.cmd, os.X_OK):
            raise GbpError, "%s not found - cannot use compare versions" % self.cmd
        gbpc.Command.__init__(self, self.cmd, ['--compare-versions'])

    def __call__(self, version1, version2):
        self.run_error = "Couldn't compare %s with %s" % (version1, version2)
        res = gbpc.Command.call(self, [ version1, 'lt', version2 ])
        if res not in [ 0, 1 ]:
            raise gbpc.CommandExecFailed, "%s: bad return code %d" % (self.run_error, res)
        if res == 0:
            return -1
        elif res == 1:
            res = gbpc.Command.call(self, [ version1, 'gt', version2 ])
            if res not in [ 0, 1 ]:
                raise gbpc.CommandExecFailed, "%s: bad return code %d" % (self.run_error, res)
            if res == 0:
                return 1
        return 0


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

def parse_changelog_repo(repo, branch, filename):
    """
    Parse the changelog file from given branch in the git
    repository.
    """
    try:
        # Note that we could just pass in the branch:filename notation
        # to show as well, but we want to check if the branch / filename
        # exists first, so we can give a separate error from other
        # repository errors.
        sha = repo.rev_parse("%s:%s" % (branch, filename), quiet=True)
    except GitRepositoryError:
        raise NoChangelogError, "Changelog %s not found in branch %s" % (filename, branch)

    lines = repo.show(sha)
    return parse_changelog('\n'.join(lines))

def parse_changelog(contents=None, filename=None):
    """
    Parse the content of a changelog file. Either contents, containing
    the contents of a changelog file, or filename, pointing to a
    changelog file must be passed.

    Returns:

    cp['Version']: full version string including epoch
    cp['Upstream-Version']: upstream version, if not debian native
    cp['Debian-Version']: debian release
    cp['Epoch']: epoch, if any
    cp['NoEpoch-Version']: full version string excluding epoch
    """
    # Check that either contents or filename is passed (but not both)
    if (not filename and not contents) or (filename and contents):
        raise Exception("Either filename or contents must be passed to parse_changelog")

    # If a filename was passed, check if it exists
    if filename and not os.access(filename, os.F_OK):
        raise NoChangelogError, "Changelog %s not found" % (filename, )

    # If no filename was passed, let parse_changelog read from stdin
    if not filename:
        filename = '-'

    # Note that if contents is None, stdin will just be closed right
    # away by communicate.
    cmd = subprocess.Popen(['dpkg-parsechangelog', '-l%s' % filename], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (output, errors) = cmd.communicate(contents)
    if cmd.returncode:
        raise ParseChangeLogError, "Failed to parse changelog.  dpkg-parsechangelog said:\n%s" % (errors, )
    # Parse the result of dpkg-parsechangelog (which looks like
    # email headers)
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

def is_valid_packagename(name):
    "Is this a valid Debian package name?"
    return packagename_re.match(name)

def is_valid_upstreamversion(version):
    "Is this a valid upstream version number?"
    return upstreamversion_re.match(version)

def get_compression(orig_file):
    "Given an orig file return the compression used"
    ext = orig_file.rsplit('.',1)[1]
    for (c, o) in compressor_opts.iteritems():
        if o[1] == ext:
            return c
    return None


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
    """invoke uscan to fetch a new upstream version"""
    p = subprocess.Popen(['uscan', '--symlink', '--destdir=..', '--dehs'], stdout=subprocess.PIPE)
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


def guess_upstream_version(archive, extra_regex=r''):
    """
    guess the package name and version from the filename of an upstgream
    archive. Returns a tuple with package name and version, or None.
    @archive: filename to guess to version for
    @extra_regex: additional regex to apply, needs a 'package' and a
    'version' group

    >>> guess_upstream_version('foo-bar_0.2.orig.tar.gz')
    ('foo-bar', '0.2')
    >>> guess_upstream_version('foo-Bar_0.2.orig.tar.gz')
    >>> guess_upstream_version('git-bar-0.2.tar.gz')
    ('git-bar', '0.2')
    >>> guess_upstream_version('git-bar-0.2-rc1.tar.gz')
    ('git-bar', '0.2-rc1')
    >>> guess_upstream_version('git-bar-0.2:~-rc1.tar.gz')
    ('git-bar', '0.2:~-rc1')
    >>> guess_upstream_version('git-Bar-0A2d:rc1.tar.bz2')
    ('git-Bar', '0A2d:rc1')
    >>> guess_upstream_version('git-1.tar.bz2')
    ('git', '1')
    >>> guess_upstream_version('kvm_87+dfsg.orig.tar.gz')
    ('kvm', '87+dfsg')
    >>> guess_upstream_version('foo-Bar_0.2.orig.tar.gz')
    >>> guess_upstream_version('foo-Bar-a.b.tar.gz')

    """
    version_chars = r'[a-zA-Z\d\.\~\-\:\+]'
    extensions = r'\.tar\.(gz|bz2)'

    version_filters = map ( lambda x: x % (version_chars, extensions),
                       ( # Debian package_<version>.orig.tar.gz:
                         r'^(?P<package>[a-z\d\.\+\-]+)_(?P<version>%s+)\.orig%s',
                         # Upstream package-<version>.tar.gz:
                         r'^(?P<package>[a-zA-Z\d\.\+\-]+)-(?P<version>[0-9]%s*)%s'))
    if extra_regex:
        version_filters = extra_regex + version_filters

    for filter in version_filters:
        m = re.match(filter, os.path.basename(archive))
        if m:
            return (m.group('package'), m.group('version'))


def compare_versions(version1, version2):
    """compares to Debian versionnumbers suitable for sort()"""
    return DpkgCompareVersions()(version1, version2)


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
