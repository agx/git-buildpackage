# -*- coding: utf-8 -*-
# utility functions for git-buildpackge and friends
# (C) 2006 Guido Guenther <agx@sigxcpu.org>

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
    cl=email.message_from_string(output)
    if '-' in cl['Version']:
        cl['Upstream-Version'], cl['Debian-Version'] = cl['Version'].rsplit('-',1)
    else:
        cl['Debian-Version']=cl['Version']
    return cl
 

def orig_file(cp):
    "The name of the orig.tar.gz belonging to changelog cp"
    return "%s_%s.orig.tar.gz" % (cp['Source'], cp['Upstream-Version'])


def is_native(cp):
    "Is this a debian native package"
    return [ True, False ]['-' in cp['Version']]


def has_orig(cp, dir):
    "Check if orig.tar.gz exists in dir"
    try:
        os.stat("%s%s" % (dir,orig_file(cp)))
    except OSError:
        return False
    return True

# vim:et:ts=4:sw=4:
