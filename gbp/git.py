# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007,2008,2011 Guido Guenther <agx@sigxcpu.org>
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""provides git repository related helpers"""

import re
import subprocess
import os.path
from command_wrappers import (GitCommand, GitInit, GitAdd, GitBranch, copy_from)
from errors import GbpError
import log
import dateutil.parser
import calendar

class GitRepositoryError(Exception):
    """Exception thrown by L{GitRepository}"""
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

    def __build_env(self, extra_env):
        """Prepare environment for subprocess calls"""
        env = None
        if extra_env is not None:
            env = os.environ.copy()
            env.update(extra_env)
        return env

    def __git_getoutput(self, command, args=[], extra_env=None, cwd=None):
        """exec a git command and return the output"""
        output = []

        env = self.__build_env(extra_env)
        cmd = ['git', command] + args
        log.debug(cmd)
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env, cwd=cwd)
        while popen.poll() == None:
            output += popen.stdout.readlines()
        ret = popen.poll()
        output += popen.stdout.readlines()
        return output, ret

    def __git_inout(self, command, args, input, extra_env=None):
        """Send input and return output (stdout)"""
        env = self.__build_env(extra_env)
        cmd = ['git', command] + args
        log.debug(cmd)
        popen = subprocess.Popen(cmd,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 env=env)
        (stdout, stderr) = popen.communicate(input)
        return stdout, stderr, popen.returncode

    def base_dir(self):
        """Base of the repository"""
        return os.path.join(self.path, '.git')

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


    def _build_legacy_tag(self, format, version):
        """legacy version numbering"""
        if ':' in version: # strip of any epochs
            version = version.split(':', 1)[1]
        version = version.replace('~', '.')
        return format % dict(version=version)


    def find_version(self, format, version):
        """
        Check if a certain version is stored in this repo. Return it's SHA1 in
        this case. For legacy tags Don't check only the tag but also the
        message, since the former wasn't injective until recently.
        You only need to use this funciton if you also need to check for legacy
        tags.

        @param format: tag pattern
        @param version: debian version number
        @return: sha1 of the version tag
        """
        tag = build_tag(format, version)
        legacy_tag = self._build_legacy_tag(format, version)
        if self.has_tag(tag): # new tags are injective
            return self.rev_parse(tag)
        elif self.has_tag(legacy_tag):
            out, ret = self.__git_getoutput('cat-file', args=['-p', legacy_tag])
            if ret:
                return None
            for line in out:
                if line.endswith(" %s\n" % version):
                    return self.rev_parse(legacy_tag)
                elif line.startswith('---'): # GPG signature start
                    return None
        return None


    def remove_tag(self, tag):
        """remove a tag 'tag'"""
        self.__check_path()
        if self.has_tag(tag):
            GitCommand("tag", [ "-d", tag ])()

    def move_tag(self, old, new):
        self.__check_path()
        GitCommand("tag", [ new, old ])()
        self.remove_tag(old)

    def get_branch(self):
        """on what branch is the current working copy"""
        self.__check_path()
        for line in self.__git_getoutput('branch', [ '--no-color' ])[0]:
            if line.startswith('*'):
                return line.split(' ', 1)[1].strip()

    def get_merge_branch(self, branch):
        """get the branch we'd merge from"""
        self.__check_path()
        try:
            remote = self.get_config("branch.%s.remote" % branch)
            merge = self.get_config("branch.%s.merge" % branch)
        except KeyError:
            return None
        remote += merge.replace("refs/heads","", 1)
        return remote

    def is_fast_forward(self, from_branch, to_branch):
        """
        check if an update from from_branch to to_branch would be a fast
        forward or if the branch is uptodate already
        @return: can_fast_forward, up_to_date
        @rtype:  tuple
        """
        has_local = False       # local repo has new commits
        has_remote = False      # remote repo has new commits
        out = self.__git_getoutput('rev-list', ["--left-right",
                                   "%s...%s" % (from_branch, to_branch),
                                   "--"])[0]

        if not out: # both branches have the same commits
            return True, True

        for line in out:
            if line.startswith("<"):
                has_local = True
            elif line.startswith(">"):
                has_remote = True

        if has_local and has_remote:
            return False, False
        elif has_local:
            return False, True
        elif has_remote:
            return True, False

    def set_branch(self, branch):
        """switch to branch 'branch'"""
        self.__check_path()
        if self.get_branch() != branch:
            GitCommand("checkout", [ branch ])()

    def create_branch(self, branch, rev=None):
        """create a new branch
           @param rev: where to start the branch from

           if param is None the branch starts form the current HEAD
        """
        self.__check_path()
        GitBranch()(branch, rev)

    def delete_branch(self, branch):
        self.__check_path()
        if self.get_branch() != branch:
            GitCommand("branch")(["-D", branch])
        else:
            raise GitRepositoryError, "Can't delete the branch you're on"

    def force_head(self, commit, hard=False):
        """force head to a specific commit"""
        args = ['--quiet']
        if hard:
            args += [ '--hard' ]
        args += [ commit, '--' ]
        GitCommand("reset")(args)

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

    def commits(self, since=None, until=None, paths=None, options=None,
                first_parent=False):
        """
        get commits from since to until touching paths

        @param options: list of options past to git log
        @type  options: list of strings
        """

        args = ['--pretty=format:%H']

        if options:
            args += options

        if first_parent:
            args += [ "--first-parent" ]

        if since and until:
            args += ['%s..%s' % (since, until)]

        if paths:
            args += [ "--", paths ]

        commits, ret = self.__git_getoutput('log', args)
        if ret:
            where = " on %s" % paths if paths else ""
            raise GitRepositoryError, ("Error getting commits %s..%s%s" %
                        (since, until, where))
        return [ commit.strip() for commit in commits ]

    def show(self, id):
        """git-show id"""
        commit, ret = self.__git_getoutput('show', [ "--pretty=medium", id ])
        if ret:
            raise GitRepositoryError, "can't get %s" % id
        for line in commit:
            yield line

    def grep_log(self, regex, where=None):
        args = ['--pretty=format:%H']
        args.append("--grep=%s" % regex)
        if where:
            args.append(where)
        args.append('--')

        commits, ret = self.__git_getoutput('log', args)
        if ret:
            raise GitRepositoryError, "Error grepping log for %s" % regex
        return [ commit.strip() for commit in commits[::-1] ]

    def get_subject(self, commit):
        """Gets the subject of a commit"""
        self.__check_path()
        out, ret =  self.__git_getoutput('log', ['-n1', '--pretty=format:%s',  commit])
        if ret:
            raise GitRepositoryError, "Error getting subject of commit %s" % commit
        return out[0].strip()

    def get_commit_info(self, commit):
        """Given a commit name, return a dictionary of its components,
        including id, author, email, subject, and body."""
        self.__check_path()
        out, ret =  self.__git_getoutput('log',
                                         ['--pretty=format:%an%n%ae%n%s%n%b%n',
                                          '-n1', commit])
        if ret:
            raise GitRepositoryError, "Unable to retrieve log entry for %s" \
                % commit
        return {'id' : commit,
                'author' : out[0].strip(),
                'email' : out[1].strip(),
                'subject' : out[2].rstrip(),
                'body' : [line.rstrip() for line in  out[3:]]}

    def find_tag(self, commit, pattern=None):
        "find the closest tag to a branch's head"
        args =  [ '--abbrev=0' ]
        if pattern:
            args += [ '--match' , pattern ]
        args += [ commit ]

        tag, ret = self.__git_getoutput('describe', args)
        if ret:
            raise GitRepositoryError, "can't find tag for %s" % commit
        return tag[0].strip()

    def rev_parse(self, name):
        "find the SHA1"
        args = [ "--quiet", "--verify", name ]
        sha, ret = self.__git_getoutput('rev-parse', args)
        if ret:
            raise GitRepositoryError, "revision '%s' not found" % name
        return sha[0].strip()

    def write_tree(self, index=None):
        """write out the current index, return the SHA1"""
        if index:
            extra_env = {'GIT_INDEX_FILE': index }
        else:
            extra_env = None

        tree, ret = self.__git_getoutput('write-tree', extra_env=extra_env)
        if ret:
            raise GitRepositoryError, "can't write out current index"
        return tree[0].strip()

    def update_ref(self, ref, new, old=None, msg=None):
        """Update ref 'ref' to commit 'new'"""
        args = [ ref, new ]
        if old:
            args += [ old ]
        if msg:
            args = [ '-m', msg ] + args
        GitCommand("update-ref")(args)

    def commit_tree(self, tree, msg, parents, author={}, committer={}):
        """Commit a tree with commit msg 'msg' and parents 'parents'"""
        extra_env = {}
        for key, val in author.items():
            if val:
                extra_env['GIT_AUTHOR_%s' % key.upper()] = val
        for key, val in committer.items():
            if val:
                extra_env['GIT_COMMITTER_%s' % key.upper()] = val

        args = [ tree ]
        for parent in parents:
            args += [ '-p' , parent ]
        sha1, stderr, ret = self.__git_inout('commit-tree', args, msg, extra_env)
        if not ret:
            return sha1.strip()
        else:
            raise GbpError, "Failed to commit tree: %s" % stderr

    def commit_dir(self, unpack_dir, msg, branch, other_parents=None,
                   author={}, committer={}):
        """Replace the current tip of branch 'branch' with the contents from 'unpack_dir'
           @param unpack_dir: content to add
           @type unpack_dir: string
           @param msg: commit message to use
           @type msg: string
           @param branch: branch to add the contents of unpack_dir to
           @type branch: string
           @param other_parents: additional parents of this commit
           @type other_parents: list string
           @param author: author information to use for commit
           @type author: dict with keys 'name', 'email', 'date'
           @param committer: committer information to use for commit
           @type committer: dict with keys 'name', 'email', 'date'"""

        self.__check_path()
        git_index_file = os.path.join(self.path, '.git', 'gbp_index')
        try:
            os.unlink(git_index_file)
        except OSError:
            pass
        extra_env = { 'GIT_INDEX_FILE': git_index_file,
                      'GIT_WORK_TREE': unpack_dir}
        GitAdd(extra_env=extra_env)(['-f', '.'])
        tree = self.write_tree(git_index_file)

        if branch:
            cur = self.rev_parse(branch)
        else: # emtpy repo
            cur = None
            branch = 'master'

        # Build list of parents:
        parents = []
        if cur:
            parents = [ cur ]
        if other_parents:
            for parent in other_parents:
                sha = self.rev_parse(parent)
                if sha not in parents:
                    parents += [ sha ]

        commit = self.commit_tree(tree=tree, msg=msg, parents=parents,
                                  author=author, committer=committer)
        if not commit:
            raise GbpError, "Failed to commit tree"
        self.update_ref("refs/heads/%s" % branch, commit, cur)
        return commit

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

    def get_remote_branches(self):
        """Get all remote branches"""
        args = [ '--format=%(refname:short)', 'refs/remotes/' ]
        out = self.__git_getoutput('for-each-ref', args)[0]
        return [ ref.strip() for ref in out ]

    def get_remote_repos(self):
        """Get all remote repositories"""
        out = self.__git_getoutput('remote')[0]
        return [ remote.strip() for remote in out ]

    def has_remote_repo(self, name):
        """Do we know about a remote named 'name'"""
        if name in self.get_remote_repos():
            return True
        else:
            return False

    def format_patches(self, start, end, output_dir):
        """
        Output the commits between start and end as patches in output_dir
        """
        options = [ '-N', '-k', '-o', output_dir, '%s...%s' % (start, end) ]
        output, ret = self.__git_getoutput('format-patch', options)
        return [ line.strip() for line in output ]

    def apply_patch(self, patch, index=True, context=None, strip=None):
        """Apply a patch using git apply"""
        args = []
        if context:
            args += [ '-C', context ]
        if index:
            args.append("--index")
        if strip:
            args += [ '-p', strip ]
        args.append(patch)
        GitCommand("apply", args)()

    def archive(self, format, prefix, output, treeish, **kwargs):
        args = [ '--format=%s' % format, '--prefix=%s' % prefix,
                 '--output=%s' % output, treeish ]
        out, ret = self.__git_getoutput('archive', args, **kwargs)
        if ret:
            raise GitRepositoryError, "unable to archive %s"%(treeish)


    def has_submodules(self):
        """Does the repo have submodules?"""
        if os.path.exists('.gitmodules'):
            return True
        else:
            return False


    def add_submodule(self, repo_path):
        """Add a submodule"""
        GitCommand("submodule", [ "add", repo_path ])()


    def update_submodules(self, init=True, recursive=True, fetch=False):
        """Update all submodules"""
        if not self.has_submodules():
            return
        args = [ "update" ]
        if recursive:
            args.append("--recursive")
        if init:
            args.append("--init")
        if not fetch:
            args.append("--no-fetch")

        GitCommand("submodule", args)()


    def get_submodules(self, treeish, path=None, recursive=True):
        """ list the submodules of treeish

            returns a list of submodule/commit-id tuples
        """
        #    Note that we is lstree instead of submodule commands because
        #    there's no way to list the submodules of another branch with
        #    the latter.
        submodules = []
        if path is None:
            path = "."

        args = [ treeish ]
        if recursive:
            args += ['-r']

        out, ret =  self.__git_getoutput('ls-tree', args, cwd=path)
        for line in out:
            mode, objtype, commit, name = line[:-1].split(None, 3)
            # A submodules is shown as "commit" object in ls-tree:
            if objtype == "commit":
                nextpath = os.path.sep.join([path, name])
                submodules.append( (nextpath, commit) )
                if recursive:
                    submodules += self.get_submodules(commit, path=nextpath,
                                                      recursive=recursive)
        return submodules


class FastImport(object):
    """Invoke git-fast-import"""
    _bufsize = 1024

    m_regular = 644
    m_exec    = 755
    m_symlink = 120000

    def __init__(self):
        try:
            self._fi = subprocess.Popen([ 'git', 'fast-import', '--quiet'], stdin=subprocess.PIPE)
            self._out = self._fi.stdin
        except OSError, err:
            raise GbpError, "Error spawning git fast-import: %s", err
        except ValueError, err:
            raise GbpError, "Invalid argument when spawning git fast-import: %s", err

    def _do_data(self, fd, size):
        self._out.write("data %s\n" % size)
        while True:
            data = fd.read(self._bufsize)
            self._out.write(data)
            if len(data) != self._bufsize:
                break
        self._out.write("\n")

    def _do_file(self, filename, mode, fd, size):
        name = "/".join(filename.split('/')[1:])
        self._out.write("M %d inline %s\n" % (mode, name))
        self._do_data(fd, size)

    def add_file(self, filename, fd, size):
        self._do_file(filename, self.m_regular, fd, size)

    def add_executable(self, filename, fd, size):
        self._do_file(filename, self.m_exec, fd, size)

    def add_symlink(self, filename, linkname):
        name = "/".join(filename.split('/')[1:])
        self._out.write("M %d inline %s\n" % (self.m_symlink, name))
        self._out.write("data %s\n" % len(linkname))
        self._out.write("%s\n" % linkname)

    def start_commit(self, branch, committer, email, time, msg):
        length = len(msg)
        self._out.write("""commit refs/heads/%(branch)s
committer %(committer)s <%(email)s> %(time)s
data %(length)s
%(msg)s
from refs/heads/%(branch)s^0
""" % locals())

    def do_deleteall(self):
        self._out.write("deleteall\n")

    def close(self):
        if self._out:
            self._out.close()
        if self._fi:
            self._fi.wait()

    def __del__(self):
        self.close()


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
    'debian/0%0_0'
    """
    return format % dict(version=__sanitize_version(version))


def __sanitize_version(version):
    """sanitize a version so git accepts it as a tag

    >>> __sanitize_version("0.0.0")
    '0.0.0'
    >>> __sanitize_version("0.0~0")
    '0.0_0'
    >>> __sanitize_version("0:0.0")
    '0%0.0'
    >>> __sanitize_version("0%0~0")
    '0%0_0'
    """
    return version.replace('~', '_').replace(':', '%')


def tag_to_version(tag, format):
    """Extract the version from a tag

    >>> tag_to_version("upstream/1%2_3-4", "upstream/%(version)s")
    '1:2~3-4'
    >>> tag_to_version("foo/2.3.4", "foo/%(version)s")
    '2.3.4'
    >>> tag_to_version("foo/2.3.4", "upstream/%(version)s")
    """
    version_re = format.replace('%(version)s',
                                '(?P<version>[\w_%+-.]+)')
    r = re.match(version_re, tag)
    if r:
        version = r.group('version').replace('_', '~').replace('%', ':')
        return version
    return None


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
