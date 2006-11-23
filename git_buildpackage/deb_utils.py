# -*- coding: utf-8 -*-
# utility functions for git-buildpackge and friends
# (C) 2006 Guido Guenther <agx@sigxcpu.org>

import email
import commands

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
 
# vim:et:ts=4:sw=4:
