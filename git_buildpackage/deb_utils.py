# -*- coding: utf-8 -*-
# (C) 2006 Guido Guenther <agx@sigxcpu.org>
"""provides some debian source package related helpers"""

import email
import commands
import os

# When trying to parse a version-number from a dsc or changes file, these are
# the valid characters.
debian_version_chars='a-zA-Z\d.~+-'

def parse_changelog(changelog):
    """parse changelog file changelog"""
    status, output = commands.getstatusoutput('dpkg-parsechangelog -l%s' % (changelog, ))
    if status:
        return None
    cp=email.message_from_string(output)
    if '-' in cp['Version']:
        cp['Upstream-Version'], cp['Debian-Version'] = cp['Version'].rsplit('-',1)
    else:
        cp['Debian-Version']=cp['Version']
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

# vim:et:ts=4:sw=4:
