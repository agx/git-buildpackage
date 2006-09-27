# utility functions for git-buildpackge and friends
# (C) 2006 Guido Guenther <agx@sigxcpu.org>

import subprocess
import os.path

def is_repository_clean(path):
    """Does the repository at path contain any uncommitted modifications"""
    try:
        dir=os.path.abspath(os.path.curdir)
        os.chdir(path)
    except OSError:
        return False
    popen = subprocess.Popen(['git','status'], stdout=subprocess.PIPE)
    status=popen.wait()
    out=popen.stdout.readlines()
    if out[0].strip() != 'nothing to commit':
        ret=False
    else:
        ret=True
    os.chdir(dir)
    return (ret, "".join(out))

# vim:et:ts=4:sw=4:
