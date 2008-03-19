# vim: set fileencoding=utf-8 :
#
# (C) 2007 Guido Guenther <agx@sigxcpu.org>
"""
Simple class wrappers for the various external commands needed by
git-buildpackage and friends
"""

import subprocess
import sys
import os.path
from errors import GbpError

class CommandExecFailed(Exception):
    """Exception raised by the Command class"""
    pass


class Command(object):
    """
    Wraps a shell command, so we don't have to store any kind of command line options in 
    one of the git-buildpackage commands
    """
    verbose = False

    def __init__(self, cmd, args=[], shell=False):
        self.cmd = cmd
        self.args = args
        self.run_error = "Couldn't run '%s'" % (" ".join([self.cmd] + self.args))
        self.shell = shell

    def __run(self, args):
        """run self.cmd adding args as additional arguments"""
        try:
            if self.verbose:
                print self.cmd, self.args, args
            cmd = [ self.cmd ] + self.args + args
            if self.shell: # subprocess.call only cares about the first argument if shell=True
                cmd = " ".join(cmd)
            retcode = subprocess.call(cmd, shell=self.shell)
            if retcode < 0:
                print >>sys.stderr, "%s was terminated by signal %d" % (self.cmd,  -retcode)
            elif retcode > 0:
                print >>sys.stderr, "%s returned %d" % (self.cmd,  retcode)
        except OSError, e:
            print >>sys.stderr, "Execution failed:", e
            retcode = 1
        if retcode:
            print >>sys.stderr, self.run_error
        return retcode

    def __call__(self, args=[]):
        if self.__run(args):
            raise CommandExecFailed


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
            raise GbpError, "%s not found - cannot use pristine-tar"
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
    def __init__(self, cmd, args=[]):
        Command.__init__(self, 'git', [cmd] + args)


class GitInitDB(GitCommand):
    """Wrap git init-db"""
    def __init__(self):
        GitCommand.__init__(self, 'init-db')
        self.run_error = "Couldn't init git repository"


class GitShowBranch(GitCommand):
    """Wrap git show-branch"""
    def __init__(self):
        GitCommand.__init__(self, 'branch')
        self.run_error = "Couldn't list branches"


class GitBranch(GitCommand):
    """Wrap git branch"""
    def __init__(self):
        GitCommand.__init__(self, 'branch')

    def __call__(self, branch):
        self.run_error = 'Couldn\'t create branch "%s"' % (branch,)
        GitCommand.__call__(self, [branch])


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


class GitTag(GitCommand):
    """Wrap git tag"""
    def __init__(self, sign_tag=False, keyid=None):
        GitCommand.__init__(self,'tag')
        self.sign_tag = sign_tag
        self.keyid = keyid

    def __call__(self, version, msg="Tagging %(version)s"):
        self.run_error = 'Couldn\'t tag "%s"' % (version,)
        if self.sign_tag:
            if self.keyid:
                sign_opts = [ '-u', self.keyid ]
            else:
                sign_opts = [ '-s' ]
        else:
            sign_opts = []
        GitCommand.__call__(self, sign_opts+[ '-m', msg % locals(), version])


class GitAdd(GitCommand):
    """Wrap git add to add new files"""
    def __init__(self):
        GitCommand.__init__(self, 'add')
        self.run_error = "Couldn't add files"


class GitRm(GitCommand):
    """Wrap git rm to remove files"""
    def __init__(self, verbose=False):
        args = [ ['-q'], [] ][verbose]
        GitCommand.__init__(self, cmd='rm', args=args)
        self.run_error = "Couldn't remove files"


class GitCommitAll(GitCommand):
    """Wrap git commit to commit all changes"""
    def __init__(self, verbose=False):
        args = ['-a'] + [ ['-q'], [] ][verbose]
        GitCommand.__init__(self, cmd='commit', args=args)

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

# vim:et:ts=4:sw=4:
