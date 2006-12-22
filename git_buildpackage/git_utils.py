# -*- coding: utf-8 -*-
#
# (C) 2006 Guido Guenther <agx@sigxcpu.org>
"""provides some git repository related helpers"""

import subprocess
import os.path
import re


def is_repository_clean():
    """Does the repository contain any uncommitted modifications"""
    clean_msg='nothing to commit'
    popen = subprocess.Popen(['git','status'], stdout=subprocess.PIPE)
    popen.wait()
    out=popen.stdout.readlines()
    if out[0].strip() == clean_msg:
        ret=True
    elif out[0].startswith('#') and out[1].strip() == clean_msg:
        ret=True
    else:
        ret=False
    return (ret, "".join(out))


def get_repository_branch():
    """on what branch is the repository"""
    popen = subprocess.Popen(['git','branch'], stdout=subprocess.PIPE)
    popen.wait()
    for line in popen.stdout:
        if line.startswith('*'):
            return line.split(' ',1)[1].strip()


def has_branch(branch):
    """check if the repository has branch branch"""
    popen = subprocess.Popen(['git','branch'], stdout=subprocess.PIPE)
    popen.wait()
    for line in popen.stdout:
        if line.split(' ',1)[1].strip() == branch:
            return True
    return False


def is_repository(path):
    """Is there a git repository at path"""
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
