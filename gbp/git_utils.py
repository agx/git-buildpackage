# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
"""provides some git repository related helpers"""

import subprocess
import os.path

class GitRepositoryError(Exception):
    """Exception thrown by GitRepository"""
    pass


class GitRepository(object):
    """Represents a git repository at path"""

    def __init__(self, path):
        try:
            os.stat(os.path.join(path,'.git'))
        except:
            raise GitRepositoryError
        self.path = os.path.abspath(path)

    
    def __check_path(self):
        if os.getcwd() != self.path:
            raise GitRepositoryError


    def __git_getoutput(self, command):
        """Exec a git command and return the output"""
        popen = subprocess.Popen(['git', command], stdout=subprocess.PIPE)
        popen.wait()
        return popen.stdout.readlines()


    def has_branch(self, branch):
        """check if the repository has branch 'branch'"""
        self.__check_path()
        for line in self.__git_getoutput('branch'):
            if line.split(' ', 1)[1].strip() == branch:
                return True
        return False


    def get_branch(self):
        """on what branch is the current working copy"""
        self.__check_path()
        for line in self.__git_getoutput('branch'):
            if line.startswith('*'):
                return line.split(' ', 1)[1].strip()
        

    def is_clean(self):
        """does the repository contain any uncommitted modifications"""
        self.__check_path()
        clean_msg = 'nothing to commit'
        out = self.__git_getoutput('status')
        if out[0].startswith('#') and out[1].strip().startswith(clean_msg):
            ret = True
        elif out[0].strip().startswith(clean_msg): # git << 1.5
            ret = True
        else:
            ret = False
        return (ret, "".join(out))


def build_tag(format, version):
    """Generate a tag from a given format and a version"""
    return format % dict(version=sanitize_version(version))


def sanitize_version(version):
    """sanitize a version so git accepts it as a tag"""
    if ':' in version: # strip of any epochs
        version = version.split(':', 1)[1]
    return version.replace('~', '.')

# vim:et:ts=4:sw=4:
