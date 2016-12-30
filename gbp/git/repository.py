# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007,2008,2011,2013 Guido Guenther <agx@sigxcpu.org>
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
#    along with this program; if not, please see
#    <http://www.gnu.org/licenses/>
"""A Git repository"""

import six
import subprocess
import os.path
import re
from collections import defaultdict

import gbp.log as log
from gbp.errors import GbpError
from gbp.git.modifier import GitModifier
from gbp.git.commit import GitCommit
from gbp.git.errors import GitError
from gbp.git.args import GitArgs


class GitRepositoryError(GitError):
    """Exception thrown by L{GitRepository}"""
    pass


class GitRemote(object):
    """Class representing a remote repository"""
    def __init__(self, name, fetch_url, push_urls):
        self._name = name
        self._fetch_url = fetch_url
        if isinstance(push_urls, six.string_types):
            self._push_urls = [push_urls]
        else:
            self._push_urls = [url for url in push_urls]

    def __str__(self):
        return self.name

    @property
    def name(self):
        """Name of the remote"""
        return self._name

    @property
    def fetch_url(self):
        """Fetch URL"""
        return self._fetch_url

    @property
    def push_urls(self):
        """List of push URLs"""
        return self._push_urls


class GitRepository(object):
    """
    Represents a git repository at I{path}. It's currently assumed that the git
    repository is stored in a directory named I{.git/} below I{path}.

    @ivar _path: The path to the working tree
    @type _path: C{str}
    @ivar _bare: Whether this is a bare repository
    @type _bare: C{bool}
    @raises GitRepositoryError: on git errors GitRepositoryError is raised by
        all methods.
    """

    def _check_bare(self):
        """Check whether this is a bare repository"""
        out, dummy, ret = self._git_inout('rev-parse', ['--is-bare-repository'],
                                          capture_stderr=True)
        if ret:
            raise GitRepositoryError(
                "Failed to get repository state at '%s'" % self.path)
        self._bare = False if out.strip() != 'true' else True
        self._git_dir = '' if self._bare else '.git'

    def __init__(self, path):
        self._path = os.path.abspath(path)
        self._bare = False
        try:
            out, dummy, ret = self._git_inout('rev-parse', ['--show-cdup'],
                                              capture_stderr=True)
            if ret or out.strip():
                raise GitRepositoryError("No Git repository at '%s': '%s'" % (self.path, out))
        except GitRepositoryError:
            raise  # We already have a useful error message
        except:
            raise GitRepositoryError("No Git repository at '%s'" % self.path)
        self._check_bare()

    @staticmethod
    def __build_env(extra_env):
        """Prepare environment for subprocess calls"""
        env = None
        if extra_env is not None:
            env = os.environ.copy()
            env.update(extra_env)
        return env

    def _git_getoutput(self, command, args=[], extra_env=None, cwd=None):
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
        @rtype: C{tuple} of C{list} of C{str} and C{int}

        @deprecated: use L{gbp.git.repository.GitRepository._git_inout} instead.
        """
        output = []

        if not cwd:
            cwd = self.path

        env = self.__build_env(extra_env)
        cmd = ['git', command] + args
        log.debug(cmd)
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env, cwd=cwd)
        while popen.poll() is None:
            output += popen.stdout.readlines()
        output += popen.stdout.readlines()
        return output, popen.returncode

    def _git_inout(self, command, args, input=None, extra_env=None, cwd=None,
                   capture_stderr=False):
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
        @param capture_stderr: whether to capture stderr
        @type capture_stderr: C{bool}
        @return: stdout, stderr, return code
        @rtype: C{tuple} of C{str}, C{str}, C{int}
        """
        if not cwd:
            cwd = self.path
        return self.__git_inout(command, args, input, extra_env, cwd, capture_stderr)

    @classmethod
    def __git_inout(cls, command, args, input, extra_env, cwd, capture_stderr):
        """
        As _git_inout but can be used without an instance
        """
        cmd = ['git', command] + args
        env = cls.__build_env(extra_env)
        stderr_arg = subprocess.PIPE if capture_stderr else None
        stdin_arg = subprocess.PIPE if input else None

        log.debug(cmd)
        popen = subprocess.Popen(cmd,
                                 stdin=stdin_arg,
                                 stdout=subprocess.PIPE,
                                 stderr=stderr_arg,
                                 env=env,
                                 close_fds=True,
                                 cwd=cwd)
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
        try:
            stdout, stderr, ret = self._git_inout(command=command,
                                                  args=args,
                                                  input=None,
                                                  extra_env=extra_env,
                                                  capture_stderr=True)
        except Exception as excobj:
            raise GitRepositoryError("Error running git %s: %s" % (command, excobj))
        if ret:
            raise GitRepositoryError("Error running git %s: %s" % (command, stderr))

    def _cmd_has_feature(self, command, feature):
        """
        Check if the git command has certain feature enabled.

        @param command: git command
        @type command: C{str}
        @param feature: feature / command option to check
        @type feature: C{str}
        @return: True if feature is supported
        @rtype: C{bool}
        """
        args = GitArgs(command, '-m')
        help, stderr, ret = self._git_inout('help',
                                            args.args,
                                            extra_env={'LC_ALL': 'C'},
                                            capture_stderr=True)
        if ret:
            raise GitRepositoryError("Invalid git command '%s': %s"
                                     % (command, stderr[:-1]))

        # Parse git command man page
        section_re = re.compile(r'^(?P<section>[A-Z].*)')
        option_re = re.compile(r'--?(?P<name>[a-zA-Z\-]+).*')
        optopt_re = re.compile(r'--\[(?P<prefix>[a-zA-Z\-]+)\]-?')
        man_section = None
        for line in help.splitlines():
            if man_section == "OPTIONS" and line.startswith('       -'):
                opts = line.split(',')
                for opt in opts:
                    opt = opt.strip()
                    match = optopt_re.match(opt)
                    if match:
                        opts.append(re.sub(optopt_re, '--', opt))
                        prefix = match.group('prefix').strip('-')
                        opt = re.sub(optopt_re, '--%s-' % prefix, opt)
                    match = option_re.match(opt)
                    if match and match.group('name') == feature:
                        return True
            # Check man section
            match = section_re.match(line)
            if match:
                man_section = match.group('section')
        return False

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
        """Whether this is a bare repository"""
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
        """SHA1 of the current HEAD"""
        return self.rev_parse('HEAD')

#{ Branches and Merging
    def rename_branch(self, branch, newbranch):
        """
        Rename branch

        @param branch: name of the branch to be renamed
        @param newbranch: new name of the branch
        """
        args = GitArgs("-m", branch, newbranch)
        self._git_command("branch", args.args)

    def create_branch(self, branch, rev=None, force=False):
        """
        Create a new branch

        @param branch: the branch's name
        @param rev: where to start the branch from
        @param force: reset branch HEAD to start point, if it already exists

        If rev is None the branch starts form the current HEAD.
        """
        args = GitArgs(branch)
        args.add_true(force, '--force')
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
        if not self.has_branch(branch):
            return

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

        @return: current branch or C{None} in an empty repo
        @rtype: C{str}
        @raises GitRepositoryError: if HEAD is not a symbolic ref
          (e.g. when in detached HEAD state)
        """
        out, dummy, ret = self._git_inout('symbolic-ref', ['HEAD'],
                                          capture_stderr=True)
        if ret:
            # We don't append stderr since
            # "fatal: ref HEAD is not a symbolic ref" confuses people
            raise GitRepositoryError("Currently not on a branch")
        ref = out.split('\n')[0]

        # Check if ref really exists
        try:
            self._git_command('show-ref', [ref])
            branch = ref[11:]  # strip /refs/heads
        except GitRepositoryError:
            branch = None  # empty repo
        return branch

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
        try:
            self._git_command('show-ref', [ref])
        except GitRepositoryError:
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
                              ['HEAD', 'refs/heads/%s' % branch])
        else:
            self._git_command("checkout", [branch])

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
        remote += merge.replace("refs/heads", "", 1)
        return remote

    def get_merge_base(self, commit1, commit2):
        """
        Get the common ancestor between two commits

        @param commit1: commit SHA1 or name of a branch or tag
        @type commit1: C{str}
        @param commit2: commit SHA1 or name of a branch or tag
        @type commit2: C{str}
        @return: SHA1 of the common ancestor
        @rtype: C{str}
        """
        args = GitArgs()
        args.add(commit1)
        args.add(commit2)
        sha1, stderr, ret = self._git_inout('merge-base',
                                            args.args,
                                            extra_env={'LC_ALL': 'C'},
                                            capture_stderr=True)
        if not ret:
            return self.strip_sha1(sha1).decode('utf-8')
        else:
            raise GitRepositoryError("Failed to get common ancestor: %s" % stderr.strip())

    def merge(self, commit, verbose=False, edit=False):
        """
        Merge changes from the named commit into the current branch

        @param commit: the commit to merge from (usually a branch name or tag)
        @type commit: C{str}
        @param verbose: whether to print a summary after the merge
        @type verbose: C{bool}
        @param edit: whether to invoke an editor to edit the merge message
        @type edit: C{bool}
        """
        args = GitArgs()
        args.add_cond(verbose, '--summary', '--no-summary')
        if (self._cmd_has_feature('merge', 'edit')):
            args.add_cond(edit, '--edit', '--no-edit')
        else:
            log.debug("Your git suite doesn't support --edit/--no-edit "
                      "option for git-merge ")
        args.add(commit)
        self._git_command("merge", args.args)

    def abort_merge(self):
        """
        Abort a merge
        """
        self._git_command("merge", ["--abort"])

    def is_fast_forward(self, from_branch, to_branch):
        """
        Check if an update I{from from_branch} to I{to_branch} would be a fast
        forward or if the branch is up to date already.

        @return: can_fast_forward, up_to_date
        @rtype: C{tuple}
        """
        has_local = False       # local repo has new commits
        has_remote = False      # remote repo has new commits
        out = self._git_getoutput('rev-list',
                                  ["--left-right",
                                   "%s...%s" % (from_branch, to_branch),
                                   "--"])[0]

        if not out:  # both branches have the same commits
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
        args = ['--format=%(refname:short)']
        args += ['refs/remotes/'] if remote else ['refs/heads/']
        out = self._git_getoutput('for-each-ref', args)[0]
        return [ref.strip() for ref in out]

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
        args = GitArgs()
        args.add_true(msg, '-m', msg)
        args.add(ref, new)
        args.add_true(old, old)
        self._git_command("update-ref", args.args)

    def branch_contains(self, branch, commit, remote=False):
        """
        Check if branch I{branch} contains commit I{commit}

        @param branch: the branch the commit should be on
        @type branch: C{str}
        @param commit: the C{str} commit to check
        @type commit: C{str}
        @param remote: whether to check remote instead of local branches
        @type remote: C{bool}
        """
        args = GitArgs()
        args.add_true(remote, '-r')
        args.add('--contains')
        args.add(commit)

        out, ret = self._git_getoutput('branch', args.args)
        for line in out:
            # remove prefix '*' for current branch before comparing
            line = line.replace('*', '')
            if line.strip() == branch:
                return True
        return False

    def set_upstream_branch(self, local_branch, upstream):
        """
        Set upstream branches for local branch

        @param local_branch: name of the local branch
        @type local_branch: C{str}
        @param upstream: remote/branch, for example origin/master
        @type upstream: C{str}
        """

        # check if both branches exist
        for branch, remote in [(local_branch, False), (upstream, True)]:
            if not self.has_branch(branch, remote=remote):
                raise GitRepositoryError("Branch %s doesn't exist!" % branch)

        if self._cmd_has_feature('branch', 'set-upstream-to'):
            args = ['--set-upstream-to=%s' % upstream, local_branch]
        else:
            args = ["--set-upstream", local_branch, upstream]

        dummy, err, ret = self._git_inout('branch',
                                          args,
                                          extra_env={'LC_ALL': 'C'},
                                          capture_stderr=True)
        if ret:
            raise GitRepositoryError(
                "Failed to set upstream branch '%s' for '%s': %s" %
                (upstream, local_branch, err.strip()))

    def get_upstream_branch(self, local_branch):
        """
        Get upstream branch for the local branch

        @param local_branch: name fo the local branch
        @type local_branch: C{str}
        @return: upstream (remote/branch) or  '' if no upstream found
        @rtype: C{str}

        """
        args = GitArgs('--format=%(upstream:short)')
        if self.has_branch(local_branch, remote=False):
            args.add('refs/heads/%s' % local_branch)
        else:
            raise GitRepositoryError("Branch %s doesn't exist!" % local_branch)

        out = self._git_getoutput('for-each-ref', args.args)[0]

        return out[0].strip()

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
        args += ['-m', msg] if msg else []
        if sign:
            args += ['-s']
            args += ['-u', keyid] if keyid else []
        args += [name]
        args += [commit] if commit else []
        self._git_command("tag", args)

    def delete_tag(self, tag):
        """
        Delete a tag named I{tag}

        @param tag: the tag to delete
        @type tag: C{str}
        """
        if self.has_tag(tag):
            self._git_command("tag", ["-d", tag])

    def move_tag(self, old, new):
        self._git_command("tag", [new, old])
        self.delete_tag(old)

    def has_tag(self, tag):
        """
        Check if the repository has a tag named I{tag}.

        @param tag: tag to look for
        @type tag: C{str}
        @return: C{True} if the repository has that tag, C{False} otherwise
        @rtype: C{bool}
        """
        out, ret = self._git_getoutput('tag', ['-l', tag])
        return [False, True][len(out)]

    def describe(self, commitish, pattern=None, longfmt=False, always=False,
                 abbrev=None, tags=False, exact_match=False):
        """
        Describe commit, relative to the latest tag reachable from it.

        @param commitish: the commit-ish to describe
        @type commitish: C{str}
        @param pattern: only look for tags matching I{pattern}
        @type pattern: C{str}
        @param longfmt: describe the commit in the long format
        @type longfmt: C{bool}
        @param always: return commit sha1 as fallback if no tag is found
        @type always: C{bool}
        @param abbrev: abbreviate sha1 to given length instead of the default
        @type abbrev: None or C{long}
        @param tags: enable matching a lightweight (non-annotated) tag
        @type tags: C{bool}
        @param exact_match: only output exact matches (a tag directly
        references the supplied commit)
        @type exact_match: C{bool}
        @return: tag name plus/or the abbreviated sha1
        @rtype: C{str}
        """
        args = GitArgs()
        args.add_true(pattern, ['--match', pattern])
        args.add_true(longfmt, '--long')
        # 'long' and 'abbrev=0' are incompatible, behave similar to
        # 'always' and 'abbrev=0'
        if longfmt and abbrev == 0:
            args.add('--abbrev=40')
        elif abbrev is not None:
            args.add('--abbrev=%s' % abbrev)
        args.add_true(always, '--always')
        args.add_true(tags, '--tags')
        args.add_true(exact_match, '--exact-match')
        args.add(commitish)

        tag, err, ret = self._git_inout('describe', args.args,
                                        extra_env={'LC_ALL': 'C'},
                                        capture_stderr=True)
        if ret:
            raise GitRepositoryError("Can't describe %s. Git error: %s" %
                                     (commitish, err.strip()))
        return tag.strip()

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
        return self.describe(commit, pattern, abbrev=0)

    def find_branch_tag(self, commit, branch, pattern=None):
        """
        Find the closest tag on a certain branch to a given commit

        @param commit: the commit to describe
        @type commit: C{str}
        @type branch: C{str}
        @param pattern: only look for tags matching I{pattern}
        @type pattern: C{str}
        @return: the found tag
        @rtype: C{str}
        """
        base_commit = self.get_merge_base(commit, branch)
        return self.describe(base_commit, pattern, abbrev=0)

    def get_tags(self, pattern=None):
        """
        List tags

        @param pattern: only list tags matching I{pattern}
        @type pattern: C{str}
        @return: tags
        @rtype: C{list} of C{str}
        """
        args = ['-l', pattern] if pattern else []
        return [line.strip() for line in self._git_getoutput('tag', args)[0]]

    def verify_tag(self, tag):
        """
        Verify a signed tag

        @param tag: the tag's name
        @type tag: C{str}
        @return: Whether the signature on the tag could be verified
        @rtype: C{bool}
        """
        args = GitArgs('-v', tag)

        try:
            self._git_command('tag', args.args)
        except GitRepositoryError:
            return False
        return True

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
            self._git_command("update-ref", [ref, commit])
        else:
            args = ['--quiet']
            if hard:
                args += ['--hard']
            args += [commit, '--']
            self._git_command("reset", args)

    def _status(self, porcelain, ignore_untracked, paths):
        args = GitArgs()
        args.add_true(ignore_untracked, '-uno')
        args.add_true(porcelain, '--porcelain')

        if paths is None:
            paths = []
        elif isinstance(paths, six.string_types):
            paths = [paths]

        out, ret = self._git_getoutput('status',
                                       args.args + paths,
                                       extra_env={'LC_ALL': 'C'})
        if ret:
            raise GitRepositoryError("Can't get repository status")
        return out

    def is_clean(self, ignore_untracked=False, paths=None):
        """
        Does the repository contain any uncommitted modifications?

        @param ignore_untracked: whether to ignore untracked files when
            checking the repository status
        @type ignore_untracked: C{bool}
        @param paths: only check changes on paths
        @type paths: C{list} of C{stings}
        @return: C{True} if the repository is clean, C{False} otherwise
            and Git's status message
        @rtype: C{tuple}
        """
        if self.bare:
            return (True, '')

        out = self._status(porcelain=True,
                           ignore_untracked=ignore_untracked,
                           paths=paths)
        if out:
            # Get a more helpful error message.
            out = self._status(porcelain=False,
                               ignore_untracked=ignore_untracked,
                               paths=paths)
            return (False, "".join(out))
        else:
            return (True, '')

    def clean(self, directories=False, force=False, dry_run=False):
        """
        Remove untracked files from the working tree.

        @param directories: remove untracked directories, too
        @type directories: C{bool}
        @param force: satisfy git configuration variable clean.requireForce
        @type force: C{bool}
        @param dry_run: don’t actually remove anything
        @type dry_run: C{bool}
        """
        options = GitArgs()
        options.add_true(directories, '-d')
        options.add_true(force, '-f')
        options.add_true(dry_run, '-n')

        _out, err, ret = self._git_inout('clean', options.args,
                                         extra_env={'LC_ALL': 'C'})
        if ret:
            raise GitRepositoryError("Can't execute repository clean: %s" % err)

    def status(self, pathlist=None):
        """
        Check status of repository.

        @param pathlist: List of paths to check status for
        @type pathlist: C{list}
        @return C{dict} of C{lists} of paths, where key is a git status flag.
        @rtype C{dict}
        """
        options = GitArgs('--porcelain', '-z')
        if pathlist:
            for path in pathlist:
                options.add(path)

        out, err, ret = self._git_inout('status', options.args,
                                        extra_env={'LC_ALL': 'C'})
        if ret:
            raise GitRepositoryError("Can't get repository status: %s" % err)

        elements = out.split('\x00')
        result = defaultdict(list)

        while elements[0] != '':
            element = elements.pop(0)
            status = element[:2]
            filepath = element[3:]
            # Expect to have two filenames for renames and copies
            if status[0] in ['R', 'C']:
                filepath = elements.pop(0) + '\x00' + filepath
            result[status].append(filepath)

        return result

    def is_empty(self):
        """
        Is the repository empty?

        @return: True if the repositorydoesn't have any commits,
            False otherwise
        @rtype: C{bool}
        """
        # an empty repo has no branches:
        return len(self.get_local_branches()) == 0

    def rev_parse(self, name, short=0):
        """
        Find the SHA1 of a given name

        @param name: the name to look for
        @type name: C{str}
        @param short:  try to abbreviate SHA1 to given length
        @type short: C{int}
        @return: the name's sha1
        @rtype: C{str}
        """
        args = GitArgs("--quiet", "--verify")
        args.add_cond(short, '--short=%d' % short)
        args.add(name)
        sha, ret = self._git_getoutput('rev-parse', args.args)
        if ret:
            raise GitRepositoryError("revision '%s' not found" % name)
        return self.strip_sha1(sha[0], short)

    @staticmethod
    def strip_sha1(sha1, length=0):
        """
        Strip a given sha1 and check if the resulting
        hash has the expected length.

        >>> GitRepository.strip_sha1('  58ef37dbeb12c44b206b92f746385a6f61253c0a\\n')
        '58ef37dbeb12c44b206b92f746385a6f61253c0a'
        >>> GitRepository.strip_sha1('58ef37d', 10)
        Traceback (most recent call last):
        ...
        GitRepositoryError: '58ef37d' is not a valid sha1 of length 10
        >>> GitRepository.strip_sha1('58ef37d', 7)
        '58ef37d'
        >>> GitRepository.strip_sha1('123456789', 7)
        '123456789'
        >>> GitRepository.strip_sha1('foobar')
        Traceback (most recent call last):
        ...
        GitRepositoryError: 'foobar' is not a valid sha1
        """
        maxlen = 40
        s = sha1.strip()

        l = length or maxlen

        if len(s) < l or len(s) > maxlen:
            raise GitRepositoryError("'%s' is not a valid sha1%s" %
                                     (s, " of length %d" % l if length else ""))
        return s

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
        _out, _err, ret = self._git_inout('ls-tree', [treeish],
                                          capture_stderr=True)
        return [True, False][ret != 0]

    def write_tree(self, index_file=None):
        """
        Create a tree object from the current index

        @param index_file: alternate index file to read changes from
        @type index_file: C{str}
        @return: the new tree object's sha1
        @rtype: C{str}
        """
        if index_file:
            extra_env = {'GIT_INDEX_FILE': index_file}
        else:
            extra_env = None

        tree, stderr, ret = self._git_inout('write-tree', [],
                                            extra_env=extra_env,
                                            capture_stderr=True)
        if ret:
            raise GitRepositoryError("Can't write out current index: %s" % stderr[:-1])
        return tree.strip()

    def make_tree(self, contents):
        """
        Create a tree based on contents. I{contents} has the same format than
        the I{GitRepository.list_tree} output.
        """
        out = ''
        args = GitArgs('-z')

        for obj in contents:
            mode, type, sha1, name = obj
            out += '%s %s %s\t%s\0' % (mode, type, sha1, name)

        sha1, err, ret = self._git_inout('mktree',
                                         args.args,
                                         out,
                                         capture_stderr=True)
        if ret:
            raise GitRepositoryError("Failed to mktree: '%s'" % err)
        return self.strip_sha1(sha1)

    def get_obj_type(self, obj):
        """
        Get type of a git repository object

        @param obj: repository object
        @type obj: C{str}
        @return: type of the repository object
        @rtype: C{str}
        """
        out, ret = self._git_getoutput('cat-file', args=['-t', obj])
        if ret:
            raise GitRepositoryError("Not a Git repository object: '%s'" % obj)
        return out[0].strip()

    def list_tree(self, treeish, recurse=False, paths=None):
        """
        Get a trees content. It returns a list of objects that match the
        'ls-tree' output: [mode, type, sha1, path].

        @param treeish: the treeish object to list
        @type treeish: C{str}
        @param recurse: whether to list the tree recursively
        @type recurse: C{bool}
        @return: the tree
        @rtype: C{list} of objects. See above.
        """
        args = GitArgs('-z')
        args.add_true(recurse, '-r')
        args.add(treeish)
        args.add("--")
        args.add_cond(paths, paths)

        out, err, ret = self._git_inout('ls-tree', args.args, capture_stderr=True)
        if ret:
            raise GitRepositoryError("Failed to ls-tree '%s': '%s'" % (treeish, err))

        tree = []
        for line in out.split('\0'):
            if line:
                tree.append(line.split(None, 3))
        return tree

#}

    def get_config(self, name):
        """
        Gets the config value associated with I{name}

        @param name: config value to get
        @return: fetched config value
        @rtype: C{str}
        """
        value, ret = self._git_getoutput('config', [name])
        if ret:
            raise KeyError
        return value[0][:-1]  # first line with \n ending removed

    def set_user_name(self, name):
        """
        Sets the full name to use for git commits.

        @param name: full name to use
        """
        args = GitArgs('user.name', name)
        self._git_command("config", args.args)

    def set_user_email(self, email):
        """
        Sets the email address to use for git commits.

        @param email: email address to use
        """
        args = GitArgs('user.email', email)
        self._git_command("config", args.args)

    def get_author_info(self):
        """
        Determine a sane values for author name and author email from git's
        config and environment variables.

        @return: name and email
        @rtype: L{GitModifier}
        """
        try:
            name = self.get_config("user.name")
        except KeyError:
            name = os.getenv("USER")
        try:
            email = self.get_config("user.email")
        except KeyError:
            email = os.getenv("EMAIL")
        email = os.getenv("GIT_AUTHOR_EMAIL", email)
        name = os.getenv("GIT_AUTHOR_NAME", name)
        return GitModifier(name, email)

#{ Remote Repositories

    def get_remotes(self):
        """
        Get a list of remote repositories

        @return: remote repositories
        @rtype: C{dict} of C{GitRemote}
        """
        out, err, ret = self._git_inout('remote', [],
                                        extra_env={'LC_ALL': 'C'},
                                        capture_stderr=True)
        if ret:
            raise GitRepositoryError('Failed to get list of remotes: %s' % err)

        # Get information about all remotes
        remotes = {}
        for remote in out.splitlines():
            out, err, _ret = self._git_inout('remote', ['show', '-n', remote],
                                             extra_env={'LC_ALL': 'C'},
                                             capture_stderr=True)
            if ret:
                raise GitRepositoryError('Failed to get information for remote '
                                         '%s: %s' % (remote, err))
            fetch_url = None
            push_urls = []
            for line in out.splitlines():
                match = re.match('\s*Fetch\s+URL:\s*(\S.*)', line)
                if match:
                    fetch_url = match.group(1)
                match = re.match('\s*Push\s+URL:\s*(\S.*)', line)
                if match:
                    push_urls.append(match.group(1))
            remotes[remote] = GitRemote(remote, fetch_url, push_urls)

        return remotes

    def get_remote_repos(self):
        """
        Get all remote repositories

        @deprecated: Use get_remotes() instead

        @return: remote repositories
        @rtype: C{list} of C{str}
        """
        out = self._git_getoutput('remote')[0]
        return [remote.strip() for remote in out]

    def has_remote_repo(self, name):
        """
        Do we know about a remote named I{name}?

        @param name: name of the remote repository
        @type name: C{str}
        @return: C{True} if the remote repositore is known, C{False} otherwise
        @rtype: C{bool}
        """
        if name in self.get_remotes():
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
        args = GitArgs('add')
        args.add_false(tags, '--no-tags')
        args.add_true(fetch, '--fetch')
        args.add(name, url)
        self._git_command("remote", args.args)

    def remove_remote_repo(self, name):
        args = GitArgs('rm', name)
        self._git_command("remote", args.args)

    def fetch(self, repo=None, tags=False, depth=0, refspec=None,
              all_remotes=False):
        """
        Download objects and refs from another repository.

        @param repo: repository to fetch from
        @type repo: C{str}
        @param tags: whether to fetch all tag objects
        @type tags: C{bool}
        @param depth: deepen the history of (shallow) repository to depth I{depth}
        @type depth: C{int}
        @param refspec: refspec to use instead of the default from git config
        @type refspec: C{str}
        @param all_remotes: fetch all remotes
        @type all_remotes: C{bool}
        """
        args = GitArgs('--quiet')
        args.add_true(tags, '--tags')
        args.add_cond(depth, '--depth=%s' % depth)
        if all_remotes:
            args.add_true(all_remotes, '--all')
        else:
            args.add_cond(repo, repo)
            args.add_cond(refspec, refspec)

        self._git_command("fetch", args.args)

    def pull(self, repo=None, ff_only=False, all_remotes=False):
        """
        Fetch and merge from another repository

        @param repo: repository to fetch from
        @type repo: C{str}
        @param ff_only: only merge if this results in a fast forward merge
        @type ff_only: C{bool}
        @param all_remotes: fetch all remotes
        @type all_remotes: C{bool}
        """
        args = GitArgs()
        args.add_true(ff_only, '--ff-only')
        if all_remotes:
            args.add_true(all_remotes, '--all')
        else:
            args.add_true(repo, repo)
        self._git_command("pull", args.args)

    def push(self, repo=None, src=None, dst=None, ff_only=True, force=False,
             tags=False, dry_run=False):
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
        @param force: force push, can cause the remote repository to lose
        commits; use it with care
        @type force: C{bool}
        @param tags: push all refs under refs/tags, in addition to other refs
        @type tags: C{bool}
        @param dry_run: dry run
        @type dry_run: C{bool}
        """
        args = GitArgs()
        args.add_cond(repo, repo)
        args.add_true(force, "-f")
        args.add_true(tags, "--tags")
        args.add_true(dry_run, "--dry-run")

        # Allow for src == '' to delete dst on the remote
        if src is not None:
            refspec = src
            if dst:
                refspec += ':%s' % dst
            if not ff_only:
                refspec = '+%s' % refspec
            args.add(refspec)

        self._git_command("push", args.args)

    def push_tag(self, repo, tag, dry_run=False):
        """
        Push a tag to the remote repo

        @param repo: repository to push to
        @type repo: C{str}
        @param tag: the name of the tag
        @type tag: C{str}
        @param dry_run: dry run
        @type dry_run: C{bool}
        """
        args = GitArgs(repo, 'tag', tag)
        args.add_true(dry_run, "--dry-run")
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

        if isinstance(paths, six.string_types):
            paths = [paths]

        args = ['-f'] if force else []

        if index_file:
            extra_env['GIT_INDEX_FILE'] = index_file

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
        if isinstance(paths, six.string_types):
            paths = [paths]

        args = [] if verbose else ['--quiet']
        self._git_command("rm", args + paths)

    def list_files(self, types=['cached']):
        """
        List files in index and working tree

        @param types: list of types to show
        @type types: C{list}
        @return: list of files
        @rtype: C{list} of C{str}
        """
        all_types = ['cached', 'deleted', 'others', 'ignored', 'stage'
                     'unmerged', 'killed', 'modified']
        args = ['-z']

        for t in types:
            if t in all_types:
                args += ['--%s' % t]
            else:
                raise GitRepositoryError("Unknown type '%s'" % t)
        out, ret = self._git_getoutput('ls-files', args)
        if ret:
            raise GitRepositoryError("Error listing files: '%d'" % ret)
        if out:
            return [file for file in out[0].split('\0') if file]
        else:
            return []

    def write_file(self, filename, filters=True):
        """
        Hash a single file and write it into the object database

        @param filename: the filename to the content of the file to hash
        @type filename: C{str}
        @param filters: whether to run filters
        @type filters: C{bool}
        @return: the hash of the file
        @rtype: C{str}
        """
        args = GitArgs('-w', '-t', 'blob')
        args.add_false(filters, '--no-filters')
        args.add(filename)

        sha1, stderr, ret = self._git_inout('hash-object',
                                            args.args,
                                            capture_stderr=True)
        if not ret:
            return self.strip_sha1(sha1)
        else:
            raise GbpError("Failed to hash %s: %s" % (filename, stderr))
#}

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
        args.add_true(edit, '--edit')
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
        args.add_true(edit, '--edit')
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
        if isinstance(files, six.string_types):
            files = [files]
        self._commit(msg=msg, args=files, author_info=author_info)

    def commit_dir(self, unpack_dir, msg, branch, other_parents=None,
                   author={}, committer={}, create_missing_branch=False):
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
            or L{GitModifier}
        @param create_missing_branch: create I{branch} as detached branch if it
            doesn't already exist.
        @type create_missing_branch: C{bool}
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
            try:
                cur = self.rev_parse(branch)
            except GitRepositoryError:
                if create_missing_branch:
                    log.debug("Will create missing branch '%s'..." % branch)
                    cur = None
                else:
                    raise
        else:  # empty repo
            cur = None
            branch = 'master'

        # Build list of parents:
        parents = []
        if cur:
            parents.append(cur)
        if other_parents:
            for parent in other_parents:
                sha = self.rev_parse(parent)
                if sha not in parents:
                    parents.append(sha)

        commit = self.commit_tree(tree=tree, msg=msg, parents=parents,
                                  author=author, committer=committer)
        if not commit:
            raise GitRepositoryError("Failed to commit tree")
        self.update_ref("refs/heads/%s" % branch, commit, cur,
                        msg="gbp: %s" % msg)
        return commit

    def commit_tree(self, tree, msg, parents, author={}, committer={}):
        """
        Commit a tree with commit msg I{msg} and parents I{parents}

        @param tree: tree to commit
        @param msg: commit message
        @param parents: parents of this commit
        @param author: authorship information
        @type author: C{dict} with keys 'name' and 'email' or L{GitModifier}
        @param committer: committer information
        @type committer: C{dict} with keys 'name' and 'email'
        """
        extra_env = {}
        for key, val in author.items():
            if val:
                extra_env['GIT_AUTHOR_%s' % key.upper()] = val
        for key, val in committer.items():
            if val:
                extra_env['GIT_COMMITTER_%s' % key.upper()] = val

        args = [tree]
        for parent in parents:
            args += ['-p', parent]
        sha1, stderr, ret = self._git_inout('commit-tree',
                                            args,
                                            msg,
                                            extra_env,
                                            capture_stderr=True)
        if not ret:
            return self.strip_sha1(sha1)
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
        if since:
            args.add("%s..%s" % (since, until or 'HEAD'))
        elif until:
            args.add(until)
        args.add_cond(options, options)
        args.add("--")
        if isinstance(paths, six.string_types):
            paths = [paths]
        args.add_cond(paths, paths)

        commits, ret = self._git_getoutput('log', args.args)
        if ret:
            where = " on %s" % paths if paths else ""
            raise GitRepositoryError("Error getting commits %s..%s%s" %
                                     (since, until, where))
        return [commit.strip() for commit in commits]

    def show(self, id):
        """git-show id"""
        obj, stderr, ret = self._git_inout('show', ["--pretty=medium", id],
                                           capture_stderr=True)
        if ret:
            raise GitRepositoryError("can't get %s: %s" % (id, stderr.rstrip()))
        return obj

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

        stdout, stderr, ret = self._git_inout('log', args,
                                              capture_stderr=True)
        if ret:
            raise GitRepositoryError("Error grepping log for %s: %s" %
                                     (regex, stderr[:-1]))
        if stdout:
            return [commit.strip() for commit in stdout.split('\n')[::-1]]
        else:
            return []

    def get_subject(self, commit):
        """
        Gets the subject of a commit.

        @deprecated: Use get_commit_info directly

        @param commit: the commit to get the subject from
        @return: the commit's subject
        @rtype: C{str}
        """
        return self.get_commit_info(commit)['subject']

    def get_commit_info(self, commitish):
        """
        Look up data of a specific commit-ish. Dereferences given commit-ish
        to the commit it points to.

        @param commitish: the commit-ish to inspect
        @return: the commit's including id, author, email, subject and body
        @rtype: dict
        """
        commit_sha1 = self.rev_parse("%s^0" % commitish)
        args = GitArgs('--pretty=format:%an%x00%ae%x00%ad%x00%cn%x00%ce%x00%cd%x00%s%x00%f%x00%b%x00',
                       '-z', '--date=raw', '--no-renames', '--name-status',
                       commit_sha1)
        out, err, ret = self._git_inout('show', args.args)
        if ret:
            raise GitRepositoryError("Unable to retrieve commit info for %s"
                                     % commitish)

        fields = out.split('\x00')

        author = GitModifier(fields[0].strip(),
                             fields[1].strip(),
                             fields[2].strip())
        committer = GitModifier(fields[3].strip(),
                                fields[4].strip(),
                                fields[5].strip())

        files = defaultdict(list)
        file_fields = fields[9:]
        # For some reason git returns one extra empty field for merge commits
        if file_fields[0] == '':
            file_fields.pop(0)
        while len(file_fields) and file_fields[0] != '':
            status = file_fields.pop(0).strip()
            path = file_fields.pop(0)
            files[status].append(path)

        return {'id': commitish,
                'author': author,
                'committer': committer,
                'subject': fields[6],
                'patchname': fields[7],
                'body': fields[8],
                'files': files}

#{ Patches
    def format_patches(self, start, end, output_dir,
                       signature=True,
                       thread=None,
                       symmetric=True):
        """
        Output the commits between start and end as patches in output_dir.

        This outputs the revisions I{start...end} by default. When using
        I{symmetric} to C{false} it uses I{start..end} instead.

        @param start: the commit on the left side of the revision range
        @param end: the commit on the right hand side of the revisino range
        @param output_dir: directory to write the patches to
        @param signature: whether to output a signature
        @param thread: whether to include In-Reply-To references
        @param symmetric: whether to use the symmetric difference (see above)
        """
        options = GitArgs('-N', '-k',
                          '-o', output_dir)
        options.add_cond(not signature, '--no-signature')
        options.add('%s%s%s' % (start, '...' if symmetric else '..', end))
        options.add_cond(thread, '--thread=%s' % thread, '--no-thread')

        output, ret = self._git_getoutput('format-patch', options.args)
        return [line.strip() for line in output]

    def apply_patch(self, patch, index=True, context=None, strip=None, fix_ws=False):
        """Apply a patch using git apply"""
        args = []
        if context:
            args += ['-C', context]
        if index:
            args.append("--index")
        if fix_ws:
            args.append("--whitespace=fix")
        if strip is not None:
            args += ['-p', str(strip)]
        args.append(patch)
        self._git_command("apply", args)

    def diff(self, obj1, obj2=None, paths=None, stat=False, summary=False,
             text=False, ignore_submodules=True):
        """
        Diff two git repository objects

        @param obj1: first object
        @type obj1: C{str}
        @param obj2: second object
        @type obj2: C{str}
        @param paths: List of paths to diff
        @type paths: C{list}
        @param stat: Show diffstat
        @type stat: C{bool} or C{int} or C{str}
        @param summary: Show diffstat
        @type summary: C{bool}
        @param text: Generate textual diffs, treat all files as text
        @type text: C{bool}
        @param ignore_submodules: ignore changes to submodules
        @type ignore_submodules: C{bool}
        @return: diff
        @rtype: C{str}
        """
        options = GitArgs('-p', '--no-ext-diff')
        if stat is True:
            options.add('--stat')
        elif stat:
            options.add('--stat=%s' % stat)
        options.add_true(summary, '--summary')
        options.add_true(text, '--text')
        options.add_true(ignore_submodules, '--ignore-submodules=all')
        options.add(obj1)
        options.add_true(obj2, obj2)
        if paths:
            options.add('--', paths)
        output, stderr, ret = self._git_inout('diff', options.args)
        if ret:
            raise GitRepositoryError("Git diff failed")
        return output

    def diff_status(self, obj1, obj2):
        """
        Get file-status of two git repository objects

        @param obj1: first object
        @type obj1: C{str}
        @param obj2: second object
        @type obj2: C{str}
        @return: name-status
        @rtype: C{defaultdict} of C{str}
        """
        options = GitArgs('--name-status', '-z', obj1, obj2)
        output, stderr, ret = self._git_inout('diff', options.args)

        elements = output.split('\x00')
        result = defaultdict(list)

        while elements[0] != '':
            status = elements.pop(0)[0]
            filepath = elements.pop(0)
            # Expect to have two filenames for renames and copies
            if status in ['R', 'C']:
                filepath = elements.pop(0) + '\x00' + filepath
            result[status].append(filepath)

        return result
#}

    def archive(self, format, prefix, output, treeish, cwd=None):
        """
        Create an archive from a treeish

        @param format: the type of archive to create, e.g. 'tar.gz'
        @type format: C{str}
        @param prefix: prefix to prepend to each filename in the archive
        @type prefix: C{str}
        @param output: the name of the archive to create
        @type output: C{str}
        @param treeish: the treeish to create the archive from
        @type treeish: C{str}
        @param cwd: The directory to run in. Defaults to the current dir
        @type cwd: C{str}
        """
        args = ['--format=%s' % format,
                '--prefix=%s' % prefix,
                '--output=%s' % output,
                treeish]
        out, err, ret = self._git_inout('archive', args, cwd=cwd, capture_stderr=True)
        if ret:
            raise GitRepositoryError("Unable to archive %s: %s" % (treeish, err.strip()))

    def collect_garbage(self, auto=False):
        """
        Cleanup unnecessary files and optimize the local repository

        param auto: only cleanup if required
        param auto: C{bool}
        """
        args = ['--auto'] if auto else []
        self._git_command("gc", args)

#{ Submodules

    def has_submodules(self, treeish=None):
        """
        Does the repo have any submodules?

        @param treeish: look into treeish
        @type treeish: C{str}
        @return: C{True} if the repository has any submodules, C{False}
            otherwise
        @rtype: C{bool}
        """
        if treeish:
            try:
                self.show('%s:.gitmodules' % treeish)
            except GitRepositoryError:
                return False
            return True
        return os.path.exists(os.path.join(self.path, '.gitmodules'))

    def add_submodule(self, repo_path):
        """
        Add a submodule

        @param repo_path: path to submodule
        @type repo_path: C{str}
        """
        self._git_command("submodule", ["add", repo_path])

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
        args = ["update"]
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
            path = self.path

        args = [treeish]
        if recursive:
            args += ['-r']

        out, err, ret = self._git_inout('ls-tree',
                                        args,
                                        cwd=path,
                                        capture_stderr=True)
        if ret:
            raise GitRepositoryError("Failed to list submodules of %s: %s" %
                                     (treeish, err.strip()))
        for line in out.split('\n'):
            if not line:
                continue
            mode, objtype, commit, name = line.split(None, 3)
            # A submodules is shown as "commit" object in ls-tree:
            if objtype == "commit":
                nextpath = os.path.join(path, name)
                submodules.append((nextpath.replace(self.path, '').lstrip('/'),
                                   commit))
                if recursive:
                    submodules += self.get_submodules(commit, path=nextpath,
                                                      recursive=recursive)
        return submodules

#{ Repository Creation

    @classmethod
    def create(cls, path, description=None, bare=False):
        """
        Create a repository at path

        @param path: where to create the repository
        @type path: C{str}
        @param bare: whether to create a bare repository
        @type bare: C{bool}
        @return: git repository object
        @rtype: L{GitRepository}
        """
        args = GitArgs()
        abspath = os.path.abspath(path)

        args.add_true(bare, '--bare')
        git_dir = '' if bare else '.git'

        try:
            if not os.path.exists(abspath):
                os.makedirs(abspath)
            try:
                stdout, stderr, ret = cls.__git_inout(command='init',
                                                      args=args.args,
                                                      input=None,
                                                      extra_env=None,
                                                      cwd=abspath,
                                                      capture_stderr=True)
            except Exception as excobj:
                raise GitRepositoryError("Error running git init: %s" % excobj)
            if ret:
                raise GitRepositoryError("Error running git init: %s" % stderr)

            if description:
                with open(os.path.join(abspath, git_dir, "description"), 'w') as f:
                    description += '\n' if description[-1] != '\n' else ''
                    f.write(description)
            return cls(abspath)
        except OSError as err:
            raise GitRepositoryError("Cannot create Git repository at '%s': %s"
                                     % (abspath, err[1]))
        return None

    @classmethod
    def clone(cls, path, remote, depth=0, recursive=False, mirror=False,
              bare=False, auto_name=True, reference=None):
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
        @param mirror: whether to pass --mirror to git-clone
        @type mirror: C{bool}
        @param bare: whether to create a bare repository
        @type bare: C{bool}
        @param auto_name: If I{True} create a directory below I{path} based on
            the I{remote}s name. Otherwise create the repo directly at I{path}.
        @type auto_name: C{bool}
        @param reference: create a clone using local objects from I{reference} repository
        @type reference: C{str}
        @return: git repository object
        @rtype: L{GitRepository}
        """
        abspath = os.path.abspath(path)
        if auto_name:
            name = None
        else:
            abspath, name = abspath.rsplit('/', 1)

        args = GitArgs('--quiet')
        args.add_true(depth, '--depth', depth)
        args.add_true(recursive, '--recursive')
        args.add_true(mirror, '--mirror')
        args.add_true(bare, '--bare')
        args.add_true(reference, '--reference', reference)
        args.add(remote)
        args.add_true(name, name)
        try:
            if not os.path.exists(abspath):
                os.makedirs(abspath)

            try:
                stdout, stderr, ret = cls.__git_inout(command='clone',
                                                      args=args.args,
                                                      input=None,
                                                      extra_env=None,
                                                      cwd=abspath,
                                                      capture_stderr=True)
            except Exception as excobj:
                raise GitRepositoryError("Error running git clone: %s" % excobj)
            if ret:
                raise GitRepositoryError("Error running git clone: %s" % stderr)

            if not name:
                try:
                    name = remote.rstrip('/').rsplit('/', 1)[1]
                except IndexError:
                    name = remote.split(':', 1)[1]
                if (mirror or bare):
                    if not name.endswith('.git'):
                        name = "%s.git" % name
                elif name.endswith('.git'):
                    name = name[:-4]
            return cls(os.path.join(abspath, name))
        except OSError as err:
            raise GitRepositoryError("Cannot clone Git repository "
                                     "'%s' to '%s': %s"
                                     % (remote, abspath, err[1]))
        return None
#}
