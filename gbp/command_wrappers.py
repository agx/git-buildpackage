# vim: set fileencoding=utf-8 :
#
# (C) 2007,2009 Guido Guenther <agx@sigxcpu.org>
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
"""
Simple class wrappers for the various external commands needed by
git-buildpackage and friends
"""

import subprocess
import os
import os.path
import signal
import gbp.log as log

class CommandExecFailed(Exception):
    """Exception raised by the Command class"""
    pass


class Command(object):
    """
    Wraps a shell command, so we don't have to store any kind of command
    line options in one of the git-buildpackage commands
    """

    def __init__(self, cmd, args=[], shell=False, extra_env=None, cwd=None):
        self.cmd = cmd
        self.args = args
        self.run_error = "Couldn't run '%s'" % (" ".join([self.cmd] +
                                                         self.args))
        self.shell = shell
        self.retcode = 1
        self.cwd = cwd
        if extra_env is not None:
            self.env = os.environ.copy()
            self.env.update(extra_env)
        else:
            self.env = None

    def __call(self, args):
        """
        Wraps subprocess.call so we can be verbose and fix python's
        SIGPIPE handling
        """
        def default_sigpipe():
            "Restore default signal handler (http://bugs.python.org/issue1652)"
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)

        log.debug("%s %s %s" % (self.cmd, self.args, args))
        cmd = [ self.cmd ] + self.args + args
        if self.shell:
            # subprocess.call only cares about the first argument if shell=True
            cmd = " ".join(cmd)
        return subprocess.call(cmd, cwd=self.cwd, shell=self.shell,
                               env=self.env, preexec_fn=default_sigpipe)

    def __run(self, args):
        """
        run self.cmd adding args as additional arguments

        Be verbose about errors and encode them in the return value, don't pass
        on exceptions.
        """
        try:
            retcode = self.__call(args)
            if retcode < 0:
                err_detail = "%s was terminated by signal %d" % (self.cmd,
                                                                 -retcode)
            elif retcode > 0:
                err_detail = "%s returned %d" % (self.cmd, retcode)
        except OSError as err:
            err_detail = "Execution failed: %s" % err
            retcode = 1
        if retcode:
            log.err("%s: %s" % (self.run_error, err_detail))
        self.retcode = retcode
        return retcode

    def __call__(self, args=[]):
        """
        Run the command, convert all errors into CommandExecFailed, assumes
        that the lower levels printed an error message - only useful if you
        only expect 0 as result.

        >>> Command("/bin/true")(["foo", "bar"])
        >>> Command("/foo/bar")()
        Traceback (most recent call last):
        ...
        CommandExecFailed
        """
        if self.__run(args):
            raise CommandExecFailed

    def call(self, args):
        """
        Like __call__ but don't use stderr and let the caller handle the
        return status

        >>> Command("/bin/true").call(["foo", "bar"])
        0
        >>> Command("/foo/bar").call(["foo", "bar"]) # doctest:+ELLIPSIS
        Traceback (most recent call last):
        ...
        CommandExecFailed: Execution failed: ...
        """
        try:
            ret = self.__call(args)
        except OSError as err:
            raise CommandExecFailed("Execution failed: %s" % err)
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


class UnpackTarArchive(Command):
    """Wrap tar to unpack a compressed tar archive"""
    def __init__(self, archive, dir, filters=[], compression=None):
        self.archive = archive
        self.dir = dir
        exclude = [("--exclude=%s" % _filter) for _filter in filters]

        if not compression:
            compression = '-a'

        Command.__init__(self, 'tar', exclude +
                         ['-C', dir, compression, '-xf', archive ])
        self.run_error = 'Couldn\'t unpack "%s"' % self.archive


class PackTarArchive(Command):
    """Wrap tar to pack a compressed tar archive"""
    def __init__(self, archive, dir, dest, filters=[], compression=None):
        self.archive = archive
        self.dir = dir
        exclude = [("--exclude=%s" % _filter) for _filter in filters]

        if not compression:
            compression = '-a'

        Command.__init__(self, 'tar', exclude +
                         ['-C', dir, compression, '-cf', archive, dest])
        self.run_error = 'Couldn\'t repack "%s"' % self.archive


class CatenateTarArchive(Command):
    """Wrap tar to catenate a tar file with the next"""
    def __init__(self, archive, **kwargs):
        self.archive = archive
        Command.__init__(self, 'tar', ['-A', '-f', archive], **kwargs)

    def __call__(self, target):
        Command.__call__(self, [target])


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


class UnpackZipArchive(Command):
    """Wrap zip to Unpack a zip file"""
    def __init__(self, archive, dir):
        self.archive = archive
        self.dir = dir

        Command.__init__(self, 'unzip', [ "-q", archive, '-d', dir ])
        self.run_error = 'Couldn\'t unpack "%s"' % self.archive


class GitCommand(Command):
    "Mother/Father of all git commands"
    def __init__(self, cmd, args=[], **kwargs):
        Command.__init__(self, 'git', [cmd] + args, **kwargs)
        self.run_error = "Couldn't run git %s" % cmd


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
