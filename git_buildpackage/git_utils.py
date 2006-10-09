# -*- coding: utf-8 -*-
# utility functions for git-buildpackge and friends
# (C) 2006 Guido Guenther <agx@sigxcpu.org>

import subprocess
import os.path

def is_repository_clean(path):
    """Does the repository at path contain any uncommitted modifications"""
    try:
        curdir=os.path.abspath(os.path.curdir)
        os.chdir(path)
    except OSError:
        return False
    popen = subprocess.Popen(['git','status'], stdout=subprocess.PIPE)
    popen.wait()
    out=popen.stdout.readlines()
    if out[0].strip() != 'nothing to commit':
        ret=False
    else:
        ret=True
    os.chdir(curdir)
    return (ret, "".join(out))

def is_repository(path):
    """Is there a git repository at path?"""
    if not path:
        return False
    try:
        os.stat(path+'/.git')
    except:
        return False
    return True

def sanitize_version(version):
    """sanitize a version so git accepts it as a tag"""
    if ':' in version: # strip of any epochs
        version=version.split(':',1)[1]
    return version.replace('~','.')

# vim:et:ts=4:sw=4:
