# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
"""provides some git repository related helpers"""

import subprocess
import os.path
from command_wrappers import (GitAdd, GitRm, copy_from)
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


    def has_branch(self, branch):
        """check if the repository has branch 'branch'"""
        self.__check_path()
        for line in self.__git_getoutput('branch', [ '--no-color' ])[0]:
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


    def is_clean(self):
        """does the repository contain any uncommitted modifications"""
        self.__check_path()
        clean_msg = 'nothing to commit'
        out = self.__git_getoutput('status')[0]
        if out[0].startswith('#') and out[1].strip().startswith(clean_msg):
            ret = True
        elif out[0].strip().startswith(clean_msg): # git << 1.5
            ret = True
        else:
            ret = False
        return (ret, "".join(out))


    def index_files(self):
        """List files in the index"""
        out, ret = self.__git_getoutput('ls-files', ['-z'])
        if ret:
            raise GitRepositoryError, "Error listing files %d" % ret
        if out:
            return [ file for file in out[0].split('\0') if file ]
        else:
            return []

    def commits(self, start, end, paths, options):
        """get commits from start to end touching pathds"""
        commits, ret = self.__git_getoutput('log', ['--pretty=format:%H',
                                            options, '%s..%s' % (start, end),
                                            '--', paths])
        if ret:
            raise GitRepositoryError, "Error gettint commits %s..%s on %s" % (start, end, paths)
        return [ commit.strip() for commit in commits ]

    def show(self, id):
        """git-show id"""
        commit, ret = self.__git_getoutput('show', [ id ])
        if ret:
            raise GitRepositoryError, "can't get %s" % id
        return commit


def build_tag(format, version):
    """Generate a tag from a given format and a version"""
    return format % dict(version=sanitize_version(version))


def sanitize_version(version):
    """sanitize a version so git accepts it as a tag"""
    if ':' in version: # strip of any epochs
        version = version.split(':', 1)[1]
    return version.replace('~', '.')


def replace_source_tree(repo, src_dir, filters, verbose=False):
        """
        make the current wc match what's in src_dir
        @return: True if wc was modified
        @rtype: boolean
        """
        old = set(repo.index_files())
        new = set(copy_from(src_dir, filters))
        GitAdd()(['.'])
        files = [ obj for obj in old - new if not os.path.isdir(obj)]
        if files:
            GitRm(verbose=verbose)(files)
        return not repo.is_clean()[0]


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
