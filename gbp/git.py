# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007,2008 Guido Guenther <agx@sigxcpu.org>
"""provides some git repository related helpers"""

import subprocess
import os.path
from command_wrappers import (GitAdd, GitRm, GitCheckoutBranch, GitInit, copy_from)
import dateutil.parser
import calendar

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

    def __git_getoutput(self, command, args=[]):
        """exec a git command and return the output"""
        output = []
        popen = subprocess.Popen(['git', command] + args, stdout=subprocess.PIPE)
        while popen.poll() == None:
            output += popen.stdout.readlines()
        ret = popen.poll()
        output += popen.stdout.readlines()
        return output, ret

    def has_branch(self, branch, remote=False):
        """
        check if the repository has branch 'branch'
        @param remote: only liste remote branches
        """
        self.__check_path()
        options = [ '--no-color' ]
        if remote:
            options += [ '-r' ]

        for line in self.__git_getoutput('branch', options)[0]:
            if line.split(' ', 1)[1].strip() == branch:
                return True
        return False

    def has_treeish(self, treeish):
        """check if the repository has the treeish object treeish"""
        self.__check_path()
        out, ret =  self.__git_getoutput('ls-tree', [ treeish ])
        return [ True, False ][ret != 0]

    def has_tag(self, tag):
        """check if the repository has the given tag"""
        self.__check_path()
        out, ret =  self.__git_getoutput('tag', [ '-l', tag ])
        return [ False, True ][len(out)]

    def get_branch(self):
        """on what branch is the current working copy"""
        self.__check_path()
        for line in self.__git_getoutput('branch', [ '--no-color' ])[0]:
            if line.startswith('*'):
                return line.split(' ', 1)[1].strip()

    def set_branch(self, branch):
        """switch to branch 'branch'"""
        self.__check_path()
        if self.get_branch() != branch:
            GitCheckoutBranch(branch)()

    def is_clean(self):
        """does the repository contain any uncommitted modifications"""
        self.__check_path()
        clean_msg = 'nothing to commit'
        out = self.__git_getoutput('status')[0]
        ret = False
        for line in out:
            if line.startswith('#'):
                continue
            if line.startswith(clean_msg):
                    ret = True
            break
        return (ret, "".join(out))

    def is_empty(self):
        """returns True if repo is empty (doesn't have any commits)"""
        # an empty repo has no branches:
        if self.get_branch():
            return False
        else:
            return True

    def index_files(self):
        """List files in the index"""
        out, ret = self.__git_getoutput('ls-files', ['-z'])
        if ret:
            raise GitRepositoryError, "Error listing files %d" % ret
        if out:
            return [ file for file in out[0].split('\0') if file ]
        else:
            return []

    def commits(self, since=None, until=None, paths=None, options=None):
        """get commits from start to end touching pathds"""

        if since or until:
            range = ['%s..%s' % (since, until)]
        else:
            range = []

        if paths:
           paths = [ "--", paths ]
        else:
            paths = []

        commits, ret = self.__git_getoutput('log',
                                            ['--pretty=format:%H'] +
                                            options +
                                            range +
                                            paths)
        if ret:
            raise GitRepositoryError, "Error getting commits %s..%s%s" % (since, until,["", " on %s" % paths][len(paths) > 0] )
        return [ commit.strip() for commit in commits[::-1] ]

    def show(self, id):
        """git-show id"""
        commit, ret = self.__git_getoutput('show', [ "--pretty=medium", id ])
        if ret:
            raise GitRepositoryError, "can't get %s" % id
        for line in commit:
            yield line

    def find_tag(self, branch):
        "find the closest tag to a branch's head"
        tag, ret = self.__git_getoutput('describe', [ "--abbrev=0", branch ])
        if ret:
            raise GitRepositoryError, "can't find tag for %s" % branch
        return tag[0].strip()

    def rev_parse(self, name):
        "find the SHA1"
        sha, ret = self.__git_getoutput('rev-parse', [ "--verify", name])
        if ret:
            raise GitRepositoryError, "can't find SHA1 for %s" % name
        return sha[0].strip()

    def write_tree(self):
        """write out the current index, return the SHA1"""
        tree, ret = self.__git_getoutput('write-tree')
        if ret:
            raise GitRepositoryError, "can't write out current index"
        return tree[0].strip()

    def replace_tree(self, src_dir, filters, verbose=False):
        """
        make the current wc match what's in src_dir
        @return: True if wc was modified
        @rtype: boolean
        """
        old = set(self.index_files())
        new = set(copy_from(src_dir, filters))
        GitAdd()(['-f', '.'])
        files = [ obj for obj in old - new if not os.path.isdir(obj)]
        if files:
            GitRm(verbose=verbose)(files)
        return not self.is_clean()[0]

    def get_config(self, name):
        """Gets the config value associated with name"""
        self.__check_path()
        value, ret = self.__git_getoutput('config', [ name ])
        if ret: raise KeyError
        return value[0][:-1] # first line with \n ending removed

    def get_author_info(self):
        try:
           name =  self.get_config("user.email")
        except KeyError:
           name = os.getenv("USER")
        try:
           email =  self.get_config("user.email")
        except KeyError:
            email = os.getenv("EMAIL")
        email = os.getenv("GIT_AUTHOR_EMAIL", email)
        name = os.getenv("GIT_AUTHOR_NAME", name)
        return (name, email)


def create_repo(path):
    """create a repository at path"""
    abspath = os.path.abspath(path)
    pwd = os.path.abspath(os.curdir)
    try:
        os.makedirs(abspath)
        os.chdir(abspath)
        GitInit()()
        return GitRepository(abspath)
    except OSError, err:
        raise GitRepositoryError, "Cannot create Git repository at %s: %s " % (path, err[1])
    finally:
        os.chdir(pwd)
    return None


def build_tag(format, version):
    """Generate a tag from a given format and a version
    >>> build_tag("debian/%(version)s", "0:0~0")
    'debian/0.0'
    """
    return format % dict(version=__sanitize_version(version))


def __sanitize_version(version):
    """sanitize a version so git accepts it as a tag
    >>> __sanitize_version("0.0.0")
    '0.0.0'
    >>> __sanitize_version("0.0~0")
    '0.0.0'
    >>> __sanitize_version("0:0.0")
    '0.0'
    """
    if ':' in version: # strip of any epochs
        version = version.split(':', 1)[1]
    return version.replace('~', '.')


def rfc822_date_to_git(rfc822_date):
    """Parse a date in RFC822 format, and convert to a 'seconds tz' string.
    >>> rfc822_date_to_git('Thu, 1 Jan 1970 00:00:01 +0000')
    '1 +0000'
    >>> rfc822_date_to_git('Thu, 20 Mar 2008 01:12:57 -0700')
    '1206000777 -0700'
    >>> rfc822_date_to_git('Sat, 5 Apr 2008 17:01:32 +0200')
    '1207407692 +0200'
    """
    d = dateutil.parser.parse(rfc822_date)
    seconds = calendar.timegm(d.utctimetuple())
    tz = d.strftime("%z")
    return '%d %s' % (seconds, tz)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
