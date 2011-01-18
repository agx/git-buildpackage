# vim: set fileencoding=utf-8 :
#
# (C) 2007,2009 Guido Guenther <agx@sigxcpu.org>
"""
Simple class wrappers for the various external commands needed by
git-buildpackage and friends
"""

import subprocess
import os
import os.path
import signal
import log
from errors import GbpError

class CommandExecFailed(Exception):
    """Exception raised by the Command class"""
    pass


class Command(object):
    """
    Wraps a shell command, so we don't have to store any kind of command line options in 
    one of the git-buildpackage commands
    """
    def __init__(self, cmd, args=[], shell=False, extra_env=None):
        self.cmd = cmd
        self.args = args
        self.run_error = "Couldn't run '%s'" % (" ".join([self.cmd] + self.args))
        self.shell = shell
        self.retcode = 1
        if extra_env is not None:
            self.env = os.environ.copy()
            self.env.update(extra_env)
        else:
            self.env = None

    def __call(self, args):
        """wraps subprocess.call so we can be verbose and fix python's SIGPIPE handling"""
        def default_sigpipe():
            "restore default signal handler (http://bugs.python.org/issue1652)"
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)

        log.debug("%s %s %s" % (self.cmd, self.args, args))
        cmd = [ self.cmd ] + self.args + args
        if self.shell: # subprocess.call only cares about the first argument if shell=True
            cmd = " ".join(cmd)
        return subprocess.call(cmd, shell=self.shell, env=self.env, preexec_fn=default_sigpipe)

    def __run(self, args):
        """
        run self.cmd adding args as additional arguments

        Be verbose about errors and encode them in the return value, don't pass
        on exceptions.
        """
        try:
            retcode = self.__call(args)
            if retcode < 0:
                log.err("%s was terminated by signal %d" % (self.cmd,  -retcode))
            elif retcode > 0:
                log.err("%s returned %d" % (self.cmd,  retcode))
        except OSError, e:
            log.err("Execution failed: " + e.__str__())
            retcode = 1
        if retcode:
            log.err(self.run_error)
        self.retcode = retcode
        return retcode

    def __call__(self, args=[]):
        """Run the command, convert all errors into CommandExecFailed, assumes
        that the lower levels printed an error message - only useful if you
        only expect 0 as result
        >>> Command("/bin/true")(["foo", "bar"])
        >>> Command("/foo/bar")()
        Traceback (most recent call last):
        ...
        CommandExecFailed
        """
        if self.__run(args):
            raise CommandExecFailed

    def call(self, args):
        """like __call__ but don't use stderr and let the caller handle the return status
        >>> Command("/bin/true").call(["foo", "bar"])
        0
        >>> Command("/foo/bar").call(["foo", "bar"]) # doctest:+ELLIPSIS
        Traceback (most recent call last):
        ...
        CommandExecFailed: Execution failed: ...
        """
        try:
            ret = self.__call(args)
        except OSError, e:
            raise CommandExecFailed, "Execution failed: %s" % e
        return ret


class RunAtCommand(Command):
    """Run a command in a specific directory"""
    def __call__(self, dir='.', *args):
        curdir = os.path.abspath(os.path.curdir)
        try:
            os.chdir(dir)
            Command.__call__(self, list(*args))
            os.chdir(curdir)
        except Exception:
            os.chdir(curdir)
            raise


class PristineTar(Command):
    cmd='/usr/bin/pristine-tar'
    branch='pristine-tar'

    def __init__(self):
        if not os.access(self.cmd, os.X_OK):
            raise GbpError, "%s not found - cannot use pristine-tar" % self.cmd
        Command.__init__(self, self.cmd)

    def commit(self, archive, branch):
        self.run_errror = 'Couldn\'t commit to "%s"' % branch
        self.__call__(['commit', archive, branch])

    def checkout(self, archive):
        self.run_errror = 'Couldn\'t checkout "%s"' % archive
        self.__call__(['checkout', archive])


class UnpackTarArchive(Command):
    """Wrap tar to Unpack a gzipped tar archive"""
    def __init__(self, archive, dir, filters=[]):
        self.archive = archive
        self.dir = dir
        exclude = [("--exclude=%s" % filter) for filter in filters]

        if archive.lower().endswith(".bz2"):
            decompress = "--bzip2"
        else:
            decompress = "--gzip"

        Command.__init__(self, 'tar', exclude + ['-C', dir, decompress, '-xf', archive ])
        self.run_error = 'Couldn\'t unpack "%s"' % self.archive


class RepackTarArchive(Command):
    """Wrap tar to Repack a gzipped tar archive"""
    def __init__(self, archive, dir, dest):
        self.archive = archive
        self.dir = dir

        if archive.lower().endswith(".bz2"):
            compress = "--bzip2"
        else:
            compress = "--gzip"

        Command.__init__(self, 'tar', ['-C', dir, compress, '-cf', archive, dest])
        self.run_error = 'Couldn\'t repack "%s"' % self.archive


class RemoveTree(Command):
    "Wrap rm to remove a whole directory tree"
    def __init__(self, tree):
        self.tree = tree
        Command.__init__(self, 'rm', [ '-rf', tree ])
        self.run_error = 'Couldn\'t remove "%s"' % self.tree


class Dch(Command):
    """Wrap dch and set a specific version"""
    def __init__(self, version, msg):
        args = ['-v', version]
        if msg:
            args.append(msg)
        Command.__init__(self, 'dch', args)
        self.run_error = "Dch failed."


class DpkgSourceExtract(Command):
    """
    Wrap dpkg-source to extract a Debian source package into a certain
    directory, this needs
    """
    def __init__(self):
        Command.__init__(self, 'dpkg-source', ['-x'])

    def __call__(self, dsc, output_dir):
        self.run_error = 'Couldn\'t extract "%s"' % dsc
        Command.__call__(self, [dsc, output_dir])


class GitCommand(Command):
    "Mother/Father of all git commands"
    def __init__(self, cmd, args=[], **kwargs):
        Command.__init__(self, 'git', [cmd] + args, **kwargs)
        self.run_error = "Couldn't run git %s" % cmd


class GitInit(GitCommand):
    """Wrap git init"""
    def __init__(self):
        GitCommand.__init__(self, 'init')
        self.run_error = "Couldn't init git repository"


class GitClone(GitCommand):
    """Wrap git clone"""
    def __init__(self):
        GitCommand.__init__(self, 'clone')
        self.run_error = "Couldn't clone git repository"


class GitShowBranch(GitCommand):
    """Wrap git show-branch"""
    def __init__(self):
        GitCommand.__init__(self, 'branch')
        self.run_error = "Couldn't list branches"


class GitBranch(GitCommand):
    """Wrap git branch"""
    def __init__(self):
        GitCommand.__init__(self, 'branch')

    def __call__(self, branch, remote=None):
        self.run_error = 'Couldn\'t create branch "%s"' % (branch,)
        options = [branch]
        if remote:
            options += [ remote ]
        GitCommand.__call__(self, options)


class GitCheckoutBranch(GitCommand):
    """Wrap git checkout in order tos switch to a certain branch"""
    def __init__(self, branch):
        GitCommand.__init__(self, 'checkout', [branch])
        self.branch = branch
        self.run_error = 'Couldn\'t switch to branch "%s"' % self.branch


class GitPull(GitCommand):
    """Wrap git pull"""
    def __init__(self, repo, branch):
        GitCommand.__init__(self, 'pull', [repo, branch]) 
        self.run_error = 'Couldn\'t pull "%s" to "%s"' % (branch, repo)


class GitFetch(GitCommand):
    """Wrap git fetch"""
    def __init__(self, remote = None):
        opts = []
        if remote:
            opts += [remote]
        GitCommand.__init__(self, 'fetch', opts)


class GitMerge(GitCommand):
    """Wrap git merge"""
    def __init__(self, branch, verbose=False):
        verbose = [ ['--no-summary'], [] ][verbose]
        GitCommand.__init__(self, 'merge', [branch] + verbose)
        self.run_error = 'Couldn\'t merge from "%s"' % (branch,)


class GitTag(GitCommand):
    """Wrap git tag"""
    def __init__(self, sign_tag=False, keyid=None):
        GitCommand.__init__(self,'tag')
        self.sign_tag = sign_tag
        self.keyid = keyid

    def __call__(self, version, msg="Tagging %(version)s", commit=None):
        self.run_error = 'Couldn\'t tag "%s"' % (version,)
        if self.sign_tag:
            if self.keyid:
                sign_opts = [ '-u', self.keyid ]
            else:
                sign_opts = [ '-s' ]
        else:
            sign_opts = []
        cmd = sign_opts + [ '-m', msg % locals(), version]
        if commit:
            cmd += [ commit ]
        GitCommand.__call__(self, cmd)


class GitAdd(GitCommand):
    """Wrap git add to add new files"""
    def __init__(self, extra_env=None):
        GitCommand.__init__(self, 'add', extra_env=extra_env)
        self.run_error = "Couldn't add files"


class GitRm(GitCommand):
    """Wrap git rm to remove files"""
    def __init__(self, verbose=False):
        args = [ ['--quiet'], [] ][verbose]
        GitCommand.__init__(self, cmd='rm', args=args)
        self.run_error = "Couldn't remove files"


class GitCommitAll(GitCommand):
    """Wrap git commit to commit all changes"""
    def __init__(self, verbose=False, **kwargs):
        args = ['-a'] + [ ['-q'], [] ][verbose]
        GitCommand.__init__(self, cmd='commit', args=args, **kwargs)

    def __call__(self, msg=''):
        args = [ [], ['-m', msg] ][len(msg) > 0]
        self.run_error = "Couldn't %s %s" % (self.cmd, " ".join(self.args + args))
        GitCommand.__call__(self, args)


def copy_from(orig_dir, filters=[]):
    """
    copy a source tree over via tar
    @param orig_dir: where to copy from
    @param exclude: tar exclude pattern
    @return: list of copied files
    @rtype: list
    """
    exclude = [("--exclude=%s" % filter) for filter in filters]

    try:
        p1 = subprocess.Popen(["tar"] + exclude + ["-cSpf", "-", "." ], stdout=subprocess.PIPE, cwd=orig_dir)
        p2 = subprocess.Popen(["tar", "-xvSpf", "-" ], stdin=p1.stdout, stdout=subprocess.PIPE)
        files = p2.communicate()[0].split('\n')
    except OSError, err:
        raise GbpError, "Cannot copy files: %s" % err
    except ValueError, err:
        raise GbpError, "Cannot copy files: %s" % err
    if p1.wait() or p2.wait():
        raise GbpError, "Cannot copy files, pipe failed."
    return [ os.path.normpath(f) for f in files if files ]

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
