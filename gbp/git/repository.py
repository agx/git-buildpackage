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
"""A Git repository"""

import re
import subprocess
import os.path

import gbp.log as log
from gbp.command_wrappers import (GitCommand, copy_from)
from gbp.errors import GbpError
from gbp.git.modifier import GitModifier
from gbp.git.commit import GitCommit
from gbp.git.errors import GitError
from gbp.git.args import GitArgs


class GitRepositoryError(GitError):
    """Exception thrown by L{GitRepository}"""
    pass


class GitRepository(object):
    """
    Represents a git repository at I{path}. It's currently assumed that the git
    repository is stored in a directory named I{.git/} below I{path}.

    @ivar _path: The path to the working tree
    @type _path: C{str}
    @ivar _bare: Whether this is a bare repository
    @type _bare: C{bool}
    """

    def _check_bare(self):
        """Check whether this is a bare repository"""
        out, ret = self.__git_getoutput('rev-parse', ['--is-bare-repository'])
        if ret:
            raise GitRepositoryError(
                "Failed to get repository state at '%s'" % self.path)
        self._bare = False if  out[0].strip() != 'true' else True
        self._git_dir = '' if self._bare else '.git'

    def __init__(self, path):
        self._path = os.path.abspath(path)
        self._bare = False
        try:
            out, ret = self.__git_getoutput('rev-parse', ['--show-cdup'])
            if ret or out not in [ ['\n'], [] ]:
                raise GitRepositoryError("No Git repository at '%s'" % self.path)
        except GitRepositoryError:
            raise # We already have a useful error message
        except:
            raise GitRepositoryError("No Git repository at '%s'" % self.path)
        self._check_bare()

    def __build_env(self, extra_env):
        """Prepare environment for subprocess calls"""
        env = None
        if extra_env is not None:
            env = os.environ.copy()
            env.update(extra_env)
        return env

    def __git_getoutput(self, command, args=[], extra_env=None, cwd=None):
        """
        Run a git command and return the output

        @param command: git command to run
        @type command: C{str}
        @param args: list of arguments
        @type args: C{list}
        @param extra_env: extra environment variables to pass
        @type extra_env: C{dict}
        @param cwd: directory to swith to when running the command, defaults to I{self.path}
        @type cwd: C{str}
        @return: stdout, return code
        @rtype: C{tuple}
        """
        output = []

        if not cwd:
            cwd = self.path

        env = self.__build_env(extra_env)
        cmd = ['git', command] + args
        log.debug(cmd)
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env, cwd=cwd)
        while popen.poll() == None:
            output += popen.stdout.readlines()
        output += popen.stdout.readlines()
        return output, popen.returncode

    def __git_inout(self, command, args, input, extra_env=None):
        """
        Run a git command with input and return output

        @param command: git command to run
        @type command: C{str}
        @param input: input to pipe to command
        @type input: C{str}
        @param args: list of arguments
        @type args: C{list}
        @param extra_env: extra environment variables to pass
        @type extra_env: C{dict}
        @return: stdout, stderr, return code
        @rtype: C{tuple}
        """
        env = self.__build_env(extra_env)
        cmd = ['git', command] + args
        log.debug(cmd)
        popen = subprocess.Popen(cmd,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 env=env,
                                 cwd=self.path)
        (stdout, stderr) = popen.communicate(input)
        return stdout, stderr, popen.returncode

    def _git_command(self, command, args=[], extra_env=None):
        """
        Execute git command with arguments args and environment env
        at path.

        @param command: git command
        @type command: C{str}
        @param args: command line arguments
        @type args: C{list}
        @param extra_env: extra environment variables to set when running command
        @type extra_env: C{dict}
        """
        GitCommand(command, args, extra_env=extra_env, cwd=self.path)()

    @property
    def path(self):
        """The absolute path to the repository"""
        return self._path

    @property
    def git_dir(self):
        """The absolute path to git's metadata"""
        return os.path.join(self.path, self._git_dir)

    @property
    def bare(self):
        """Wheter this is a bare repository"""
        return self._bare

    @property
    def tags(self):
        """List of all tags in the repository"""
        return self.get_tags()

    @property
    def branch(self):
        """The currently checked out branch"""
        try:
            return self.get_branch()
        except GitRepositoryError:
            return None

    @property
    def head(self):
        """return the SHA1 of the current HEAD"""
        return self.rev_parse('HEAD')

#{ Branches and Merging
    def create_branch(self, branch, rev=None):
        """
        Create a new branch

        @param branch: the branch's name
        @param rev: where to start the branch from

        If rev is None the branch starts form the current HEAD.
        """
        args = GitArgs(branch)
        args.add_true(rev, rev)
        self._git_command("branch", args.args)

    def delete_branch(self, branch, remote=False):
        """
        Delete branch I{branch}

        @param branch: name of the branch to delete
        @type branch: C{str}
        @param remote: delete a remote branch
        @param remote: C{bool}
        """
        args = GitArgs('-D')
        args.add_true(remote, '-r')
        args.add(branch)

        if self.branch != branch:
            self._git_command("branch", args.args)
        else:
            raise GitRepositoryError("Can't delete the branch you're on")

    def get_branch(self):
        """
        On what branch is the current working copy

        @return: current branch
        @rtype: C{str}
        """
        out, ret = self.__git_getoutput('symbolic-ref', [ 'HEAD' ])
        if ret:
            raise GitRepositoryError("Currently not on a branch")

        ref = out[0][:-1]
        # Check if ref really exists
        failed = self.__git_getoutput('show-ref', [ ref ])[1]
        if not failed:
            return ref[11:] # strip /refs/heads

    def has_branch(self, branch, remote=False):
        """
        Check if the repository has branch named I{branch}.

        @param branch: branch to look for
        @param remote: only look for remote branches
        @type remote: C{bool}
        @return: C{True} if the repository has this branch, C{False} otherwise
        @rtype: C{bool}
        """
        if remote:
            ref = 'refs/remotes/%s' % branch
        else:
            ref = 'refs/heads/%s' % branch
        failed = self.__git_getoutput('show-ref', [ ref ])[1]
        if failed:
            return False
        return True

    def set_branch(self, branch):
        """
        Switch to branch I{branch}

        @param branch: name of the branch to switch to
        @type branch: C{str}
        """
        if self.branch == branch:
            return

        if self.bare:
            self._git_command("symbolic-ref",
                              [ 'HEAD', 'refs/heads/%s' % branch ])
        else:
            self._git_command("checkout", [ branch ])

    def get_merge_branch(self, branch):
        """
        Get the branch we'd merge from

        @return: repo and branch we would merge from
        @rtype: C{str}
        """
        try:
            remote = self.get_config("branch.%s.remote" % branch)
            merge = self.get_config("branch.%s.merge" % branch)
        except KeyError:
            return None
        remote += merge.replace("refs/heads","", 1)
        return remote

    def merge(self, commit, verbose=False):
        """
        Merge changes from the named commit into the current branch

        @param commit: the commit to merge from (usually a branch name)
        @type commit: C{str}
        """
        args = [ "--summary"  ] if verbose else [ "--no-summary" ]
        self._git_command("merge", args + [ commit ])

    def is_fast_forward(self, from_branch, to_branch):
        """
        Check if an update I{from from_branch} to I{to_branch} would be a fast
        forward or if the branch is up to date already.

        @return: can_fast_forward, up_to_date
        @rtype: C{tuple}
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

    def _get_branches(self, remote=False):
        """
        Get a list of branches

        @param remote: whether to list local or remote branches
        @type remote: C{bool}
        @return: local or remote branches
        @rtype: C{list}
        """
        args = [ '--format=%(refname:short)' ]
        args += [ 'refs/remotes/' ] if remote else [ 'refs/heads/' ]
        out = self.__git_getoutput('for-each-ref', args)[0]
        return [ ref.strip() for ref in out ]

    def get_local_branches(self):
        """
        Get a list of local branches

        @return: local branches
        @rtype: C{list}
        """
        return self._get_branches(remote=False)


    def get_remote_branches(self):
        """
        Get a list of remote branches

        @return: remote branches
        @rtype: C{list}
        """
        return self._get_branches(remote=True)

    def update_ref(self, ref, new, old=None, msg=None):
        """
        Update ref I{ref} to commit I{new} if I{ref} currently points to
        I{old}

        @param ref: the ref to update
        @type ref: C{str}
        @param new: the new value for ref
        @type new: C{str}
        @param old: the old value of ref
        @type old: C{str}
        @param msg: the reason for the update
        @type msg: C{str}
        """
        args = [ ref, new ]
        if old:
            args += [ old ]
        if msg:
            args = [ '-m', msg ] + args
        self._git_command("update-ref", args)

#{ Tags

    def create_tag(self, name, msg=None, commit=None, sign=False, keyid=None):
        """
        Create a new tag.

        @param name: the tag's name
        @type name: C{str}
        @param msg: The tag message.
        @type msg: C{str}
        @param commit: the commit or object to create the tag at, default
            is I{HEAD}
        @type commit: C{str}
        @param sign: Whether to sing the tag
        @type sign: C{bool}
        @param keyid: the GPG keyid used to sign the tag
        @type keyid: C{str}
        """
        args = []
        args += [ '-m', msg ] if msg else []
        if sign:
            args += [ '-s' ]
            args += [ '-u', keyid ] if keyid else []
        args += [ name ]
        args += [ commit ] if commit else []
        self._git_command("tag", args)

    def delete_tag(self, tag):
        """
        Delete a tag named I{tag}

        @param tag: the tag to delete
        @type tag: C{str}
        """
        if self.has_tag(tag):
            self._git_command("tag", [ "-d", tag ])

    def move_tag(self, old, new):
        self._git_command("tag", [ new, old ])
        self.delete_tag(old)

    def has_tag(self, tag):
        """
        Check if the repository has a tag named I{tag}.

        @param tag: tag to look for
        @type tag: C{str}
        @return: C{True} if the repository has that tag, C{False} otherwise
        @rtype: C{bool}
        """
        out, ret =  self.__git_getoutput('tag', [ '-l', tag ])
        return [ False, True ][len(out)]

    def find_tag(self, commit, pattern=None):
        """
        Find the closest tag to a given commit

        @param commit: the commit to describe
        @type commit: C{str}
        @param pattern: only look for tags matching I{pattern}
        @type pattern: C{str}
        @return: the found tag
        @rtype: C{str}
        """
        args =  [ '--abbrev=0' ]
        if pattern:
            args += [ '--match' , pattern ]
        args += [ commit ]

        tag, ret = self.__git_getoutput('describe', args)
        if ret:
            raise GitRepositoryError("Can't find tag for %s" % commit)
        return tag[0].strip()

    def get_tags(self, pattern=None):
        """
        List tags

        @param pattern: only list tags matching I{pattern}
        @type pattern: C{str}
        @return: tags
        @rtype: C{list} of C{str}
        """
        args = [ '-l', pattern ] if pattern else []
        return [ line.strip() for line in self.__git_getoutput('tag', args)[0] ]
#}
    def force_head(self, commit, hard=False):
        """
        Force HEAD to a specific commit

        @param commit: commit to move HEAD to
        @param hard: also update the working copy
        @type hard: C{bool}
        """
        if not GitCommit.is_sha1(commit):
            commit = self.rev_parse(commit)

        if self.bare:
            ref = "refs/heads/%s" % self.get_branch()
            self._git_command("update-ref", [ ref, commit ])
        else:
            args = ['--quiet']
            if hard:
                args += [ '--hard' ]
            args += [ commit, '--' ]
            self._git_command("reset", args)

    def is_clean(self):
        """
        Does the repository contain any uncommitted modifications?

        @return: C{True} if the repository is clean, C{False} otherwise
            and Git's status message
        @rtype: C{tuple}
        """
        if self.bare:
            return (True, '')

        clean_msg = 'nothing to commit'
        out, ret = self.__git_getoutput('status')
        if ret:
            raise GbpError("Can't get repository status")
        ret = False
        for line in out:
            if line.startswith('#'):
                continue
            if line.startswith(clean_msg):
                ret = True
            break
        return (ret, "".join(out))

    def is_empty(self):
        """
        Is the repository empty?

        @return: True if the repositorydoesn't have any commits,
            False otherwise
        @rtype: C{bool}
        """
        # an empty repo has no branches:
        return False if self.branch else True

    def rev_parse(self, name):
        """
        Find the SHA1 of a given name

        @param name: the name to look for
        @type name: C{str}
        @return: the name's sha1
        @rtype: C{str}
        """
        args = [ "--quiet", "--verify", name ]
        sha, ret = self.__git_getoutput('rev-parse', args)
        if ret:
            raise GitRepositoryError("revision '%s' not found" % name)
        return sha[0].strip()

#{ Trees
    def checkout(self, treeish):
        """
        Checkout treeish

        @param treeish: the treeish to check out
        @type treeish: C{str}
        """
        self._git_command("checkout", ["--quiet", treeish])

    def has_treeish(self, treeish):
        """
        Check if the repository has the treeish object I{treeish}.

        @param treeish: treeish object to look for
        @type treeish: C{str}
        @return: C{True} if the repository has that tree, C{False} otherwise
        @rtype: C{bool}
        """

        out, ret =  self.__git_getoutput('ls-tree', [ treeish ])
        return [ True, False ][ret != 0]

    def write_tree(self, index_file=None):
        """
        Create a tree object from the current index

        @param index_file: alternate index file to write the current index to
        @type index_file: C{str}
        @return: the new tree object's sha1
        @rtype: C{str}
        """
        if index_file:
            extra_env = {'GIT_INDEX_FILE': index_file }
        else:
            extra_env = None

        tree, ret = self.__git_getoutput('write-tree', extra_env=extra_env)
        if ret:
            raise GitRepositoryError("Can't write out current index")
        return tree[0].strip()
#}

    def get_config(self, name):
        """
        Gets the config value associated with I{name}

        @param name: config value to get
        @return: fetched config value
        @rtype: C{str}
        """
        value, ret = self.__git_getoutput('config', [ name ])
        if ret: raise KeyError
        return value[0][:-1] # first line with \n ending removed

    def get_author_info(self):
        """
        Determine a sane values for author name and author email from git's
        config and environment variables.

        @return: name and email
        @rtype: L{GitModifier}
        """
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
        return GitModifier(name, email)

#{ Remote Repositories

    def get_remote_repos(self):
        """
        Get all remote repositories

        @return: remote repositories
        @rtype: C{list} of C{str}
        """
        out = self.__git_getoutput('remote')[0]
        return [ remote.strip() for remote in out ]

    def has_remote_repo(self, name):
        """
        Do we know about a remote named I{name}?

        @param name: name of the remote repository
        @type name: C{str}
        @return: C{True} if the remote repositore is known, C{False} otherwise
        @rtype: C{bool}
        """
        if name in self.get_remote_repos():
            return True
        else:
            return False

    def add_remote_repo(self, name, url, tags=True, fetch=False):
        """
        Add a tracked remote repository

        @param name: the name to use for the remote
        @type name: C{str}
        @param url: the url to add
        @type url: C{str}
        @param tags: whether to fetch tags
        @type tags: C{bool}
        @param fetch: whether to fetch immediately from the remote side
        @type fetch: C{bool}
        """
        args = [ "add" ]
        args += [ '--tags' ] if tags else [ '--no-tags']
        args += [ '--fetch' ] if fetch else []
        args += [ name, url ]
        self._git_command("remote", args)

    def fetch(self, repo=None):
        """
        Download objects and refs from another repository.

        @param repo: repository to fetch from
        @type repo: C{str}
        """
        args =  [ '--quiet' ]
        args += [repo] if repo else []

        self._git_command("fetch", args)

    def pull(self, repo=None, ff_only=False):
        """
        Fetch and merge from another repository

        @param repo: repository to fetch from
        @type repo: C{str}
        @param ff_only: only merge if this results in a fast forward merge
        @type ff_only: C{bool}
        """
        args = []
        args += [ '--ff-only' ] if ff_only else []
        args += [ repo ] if repo else []
        self._git_command("pull", args)

    def push(self, repo=None, src=None, dst=None, ff_only=True):
        """
        Push changes to the remote repo

        @param repo: repository to push to
        @type repo: C{str}
        @param src: the source ref to push
        @type src: C{str}
        @param dst: the name of the destination ref to push to
        @type dst: C{str}
        @param ff_only: only push if it's a fast forward update
        @type ff_only: C{bool}
        """
        args = GitArgs()
        args.add_cond(repo, repo)

        # Allow for src == '' to delete dst on the remote
        if src != None:
            refspec = src
            if dst:
                refspec += ':%s' % dst
            if not ff_only:
                refspec = '+%s' % refspec
            args.add(refspec)
        self._git_command("push", args.args)

    def push_tag(self, repo, tag):
        """
        Push a tag to the remote repo

        @param repo: repository to push to
        @type repo: C{str}
        @param tag: the name of the tag
        @type tag: C{str}
        """
        args = GitArgs(repo, 'tag', tag)
        self._git_command("push", args.args)

#{ Files

    def add_files(self, paths, force=False, index_file=None, work_tree=None):
        """
        Add files to a the repository

        @param paths: list of files to add
        @type paths: list or C{str}
        @param force: add files even if they would be ignored by .gitignore
        @type force: C{bool}
        @param index_file: alternative index file to use
        @param work_tree: alternative working tree to use
        """
        extra_env = {}

        if isinstance(paths, basestring):
            paths = [ paths ]

        args = [ '-f' ] if force else []

        if index_file:
            extra_env['GIT_INDEX_FILE'] =  index_file

        if work_tree:
            extra_env['GIT_WORK_TREE'] = work_tree

        self._git_command("add", args + paths, extra_env)

    def remove_files(self, paths, verbose=False):
        """
        Remove files from the repository

        @param paths: list of files to remove
        @param paths: C{list} or C{str}
        @param verbose: be verbose
        @type verbose: C{bool}
        """
        if isinstance(paths, basestring):
            paths = [ paths ]

        args =  [] if verbose else ['--quiet']
        self._git_command("rm", args + paths)

    def list_files(self, types=['cached']):
        """
        List files in index and working tree

        @param types: list of types to show
        @type types: C{list}
        @return: list of files
        @rtype: C{list} of C{str}
        """
        all_types = [ 'cached', 'deleted', 'others', 'ignored',  'stage'
                      'unmerged', 'killed', 'modified' ]
        args = [ '-z' ]

        for t in types:
            if t in all_types:
                args += [ '--%s' % t ]
            else:
                raise GitRepositoryError("Unknown type '%s'" % t)
        out, ret = self.__git_getoutput('ls-files', args)
        if ret:
            raise GitRepositoryError("Error listing files: '%d'" % ret)
        if out:
            return [ file for file in out[0].split('\0') if file ]
        else:
            return []

#{ Comitting

    def _commit(self, msg, args=[], author_info=None):
        extra_env = author_info.get_author_env() if author_info else None
        self._git_command("commit", ['-q', '-m', msg] + args, extra_env=extra_env)

    def commit_staged(self, msg, author_info=None, edit=False):
        """
        Commit currently staged files to the repository

        @param msg: commit message
        @type msg: C{str}
        @param author_info: authorship information
        @type author_info: L{GitModifier}
        @param edit: whether to spawn an editor to edit the commit info
        @type edit: C{bool}
        """
        args = GitArgs()
        args.add_true(edit,  '--edit')
        self._commit(msg=msg, args=args.args, author_info=author_info)

    def commit_all(self, msg, author_info=None, edit=False):
        """
        Commit all changes to the repository
        @param msg: commit message
        @type msg: C{str}
        @param author_info: authorship information
        @type author_info: L{GitModifier}
        """
        args = GitArgs('-a')
        args.add_true(edit,  '--edit')
        self._commit(msg=msg, args=args.args, author_info=author_info)

    def commit_files(self, files, msg, author_info=None):
        """
        Commit the given files to the repository

        @param files: file or files to commit
        @type files: C{str} or C{list}
        @param msg: commit message
        @type msg: C{str}
        @param author_info: authorship information
        @type author_info: L{GitModifier}
        """
        if isinstance(files, basestring):
            files = [ files ]
        self._commit(msg=msg, args=files, author_info=author_info)

    def commit_dir(self, unpack_dir, msg, branch, other_parents=None,
                   author={}, committer={}):
        """
        Replace the current tip of branch I{branch} with the contents from I{unpack_dir}

        @param unpack_dir: content to add
        @type unpack_dir: C{str}
        @param msg: commit message to use
        @type msg: C{str}
        @param branch: branch to add the contents of unpack_dir to
        @type branch: C{str}
        @param other_parents: additional parents of this commit
        @type other_parents: C{list} of C{str}
        @param author: author information to use for commit
        @type author: C{dict} with keys I{name}, I{email}, I{date}
        @param committer: committer information to use for commit
        @type committer: C{dict} with keys I{name}, I{email}, I{date}
        """

        git_index_file = os.path.join(self.path, self._git_dir, 'gbp_index')
        try:
            os.unlink(git_index_file)
        except OSError:
            pass
        self.add_files('.', force=True, index_file=git_index_file,
                       work_tree=unpack_dir)
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
            raise GbpError("Failed to commit tree")
        self.update_ref("refs/heads/%s" % branch, commit, cur)
        return commit

    def commit_tree(self, tree, msg, parents, author={}, committer={}):
        """
        Commit a tree with commit msg I{msg} and parents I{parents}

        @param tree: tree to commit
        @param msg: commit message
        @param parents: parents of this commit
        @param author: authorship information
        @type author: C{dict} with keys 'name' and 'email'
        @param committer: comitter information
        @type committer: C{dict} with keys 'name' and 'email'
        """
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
            raise GbpError("Failed to commit tree: %s" % stderr)

#{ Commit Information

    def get_commits(self, since=None, until=None, paths=None, num=0,
                    first_parent=False, options=None):
        """
        Get commits from since to until touching paths

        @param since: commit to start from
        @type since: C{str}
        @param until: last commit to get
        @type until: C{str}
        @param paths: only list commits touching paths
        @type paths: C{list} of C{str}
        @param num: maximum number of commits to fetch
        @type num: C{int}
        @param options: list of additional options passed to git log
        @type  options: C{list} of C{str}ings
        @param first_parent: only follow first parent when seeing a
                             merge commit
        @type first_parent: C{bool}
        """
        args = GitArgs('--pretty=format:%H')
        args.add_true(num, '-%d' % num)
        args.add_true(first_parent, '--first-parent')
        args.add_true(since and until, '%s..%s' % (since, until))
        args.add_cond(options, options)
        args.add("--")
        if isinstance(paths, basestring):
            paths = [ paths ]
        args.add_cond(paths, paths)

        commits, ret = self.__git_getoutput('log', args.args)
        if ret:
            where = " on %s" % paths if paths else ""
            raise GitRepositoryError, ("Error getting commits %s..%s%s" %
                        (since, until, where))
        return [ commit.strip() for commit in commits ]

    def show(self, id):
        """git-show id"""
        commit, ret = self.__git_getoutput('show', [ "--pretty=medium", id ])
        if ret:
            raise GitRepositoryError("can't get %s" % id)
        for line in commit:
            yield line

    def grep_log(self, regex, since=None):
        """
        Get commmits matching I{regex}

        @param regex: regular expression
        @type regex: C{str}
        @param since: where to start grepping (e.g. a branch)
        @type since: C{str}
        """
        args = ['--pretty=format:%H']
        args.append("--grep=%s" % regex)
        if since:
            args.append(since)
        args.append('--')

        commits, ret = self.__git_getoutput('log', args)
        if ret:
            raise GitRepositoryError("Error grepping log for %s" % regex)
        return [ commit.strip() for commit in commits[::-1] ]

    def get_subject(self, commit):
        """
        Gets the subject of a commit.

        @param commit: the commit to get the subject from
        @return: the commit's subject
        @rtype: C{str}
        """
        out, ret =  self.__git_getoutput('log', ['-n1', '--pretty=format:%s',  commit])
        if ret:
            raise GitRepositoryError("Error getting subject of commit %s"
                                     % commit)
        return out[0].strip()

    def get_commit_info(self, commit):
        """
        Look up data of a specific  commit

        @param commit: the commit to inspect
        @return: the commit's including id, author, email, subject and body
        @rtype: dict
        """
        out, ret =  self.__git_getoutput('log',
                                         ['--pretty=format:%an%n%ae%n%s%n%b%n',
                                          '-n1', commit])
        if ret:
            raise GitRepositoryError("Unable to retrieve log entry for %s"
                                     % commit)
        return {'id' : commit,
                'author' : out[0].strip(),
                'email' : out[1].strip(),
                'subject' : out[2].rstrip(),
                'body' : [line.rstrip() for line in  out[3:]]}


#{ Patches
    def format_patches(self, start, end, output_dir, signature=True):
        """
        Output the commits between start and end as patches in output_dir
        """
        options = GitArgs('-N', '-k',
                          '-o', output_dir)
        options.add_cond(not signature, '--no-signature')
        options.add('%s...%s' % (start, end))

        output, ret = self.__git_getoutput('format-patch', options.args)
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
        self._git_command("apply", args)
#}

    def archive(self, format, prefix, output, treeish, **kwargs):
        args = [ '--format=%s' % format, '--prefix=%s' % prefix,
                 '--output=%s' % output, treeish ]
        out, ret = self.__git_getoutput('archive', args, **kwargs)
        if ret:
            raise GitRepositoryError("Unable to archive %s" % treeish)

    def collect_garbage(self, auto=False):
        """
        Cleanup unnecessary files and optimize the local repository

        param auto: only cleanup if required
        param auto: C{bool}
        """
        args = [ '--auto' ] if auto else []
        self._git_command("gc", args)

#{ Submodules

    def has_submodules(self):
        """
        Does the repo have any submodules?

        @return: C{True} if the repository has any submodules, C{False}
            otherwise
        @rtype: C{bool}
        """
        if os.path.exists('.gitmodules'):
            return True
        else:
            return False


    def add_submodule(self, repo_path):
        """
        Add a submodule

        @param repo_path: path to submodule
        @type repo_path: C{str}
        """
        self._git_command("submodule", [ "add", repo_path ])


    def update_submodules(self, init=True, recursive=True, fetch=False):
        """
        Update all submodules

        @param init: whether to initialize the submodule if necessary
        @type init: C{bool}
        @param recursive: whether to update submodules recursively
        @type recursive: C{bool}
        @param fetch: whether to fetch new objects
        @type fetch: C{bool}
        """

        if not self.has_submodules():
            return
        args = [ "update" ]
        if recursive:
            args.append("--recursive")
        if init:
            args.append("--init")
        if not fetch:
            args.append("--no-fetch")

        self._git_command("submodule", args)


    def get_submodules(self, treeish, path=None, recursive=True):
        """
        List the submodules of treeish

        @return: a list of submodule/commit-id tuples
        @rtype: list of tuples
        """
        # Note that we is lstree instead of submodule commands because
        # there's no way to list the submodules of another branch with
        # the latter.
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

#{ Repository Creation

    @classmethod
    def create(klass, path, description=None, bare=False):
        """
        Create a repository at path

        @param path: where to create the repository
        @type path: C{str}
        @return: git repository object
        @rtype: L{GitRepository}
        """
        abspath = os.path.abspath(path)

        if bare:
            args = [ '--bare' ]
            git_dir = ''
        else:
            args = []
            git_dir = '.git'

        try:
            if not os.path.exists(abspath):
                os.makedirs(abspath)
            GitCommand("init", args, cwd=abspath)()
            if description:
                with file(os.path.join(abspath, git_dir, "description"), 'w') as f:
                    description += '\n' if description[-1] != '\n' else ''
                    f.write(description)
            return klass(abspath)
        except OSError, err:
            raise GitRepositoryError("Cannot create Git repository at '%s': %s"
                                     % (abspath, err[1]))
        return None

    @classmethod
    def clone(klass, path, remote, depth=0, recursive=False, mirror=False,
              bare=False, auto_name=True):
        """
        Clone a git repository at I{remote} to I{path}.

        @param path: where to clone the repository to
        @type path: C{str}
        @param remote: URL to clone
        @type remote: C{str}
        @param depth: create a shallow clone of depth I{depth}
        @type depth: C{int}
        @param recursive: whether to clone submodules
        @type recursive: C{bool}
        @param auto_name: If I{True} create a directory below I{path} based on
            the I{remote}s name. Otherwise create the repo directly at I{path}.
        @type auto_name: C{bool}
        @return: git repository object
        @rtype: L{GitRepository}
        """
        abspath = os.path.abspath(path)
        if auto_name:
            name = None
        else:
            abspath, name = abspath.rsplit('/', 1)

        args = GitArgs('--quiet')
        args.add_true(depth,  '--depth', depth)
        args.add_true(recursive, '--recursive')
        args.add_true(mirror, '--mirror')
        args.add_true(bare, '--bare')
        args.add(remote)
        args.add_true(name, name)
        try:
            if not os.path.exists(abspath):
                os.makedirs(abspath)

            GitCommand("clone", args.args, cwd=abspath)()
            if not name:
                name = remote.rstrip('/').rsplit('/',1)[1]
                if (mirror or bare):
                    name = "%s.git" % name
                elif name.endswith('.git'):
                    name = name[:-4]
            return klass(os.path.join(abspath, name))
        except OSError, err:
            raise GitRepositoryError("Cannot clone Git repository "
                                     "'%s' to '%s': %s"
                                     % (remote, abspath, err[1]))
        return None
#}

