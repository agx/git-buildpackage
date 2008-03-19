# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
"""provides some debian source package related helpers"""

import email
import commands
import os
import shutil
import command_wrappers as gbpc

# When trying to parse a version-number from a dsc or changes file, these are
# the valid characters.
debian_version_chars = 'a-zA-Z\d.~+-'

class NoChangelogError(Exception):
    """no changelog found"""
    pass

class ParseChangeLogError(Exception):
    """problem parsing changelog"""
    pass

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

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
