# vim: set fileencoding=utf-8 :
#
# (C) 2007,2009,2015 Guido Guenther <agx@sigxcpu.org>
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
"""
Simple class wrappers for the various external commands needed by
git-buildpackage and friends
"""

import subprocess
import os
import signal
import sys
from contextlib import contextmanager
from tempfile import TemporaryFile

import gbp.log as log


class CommandExecFailed(Exception):
    """Exception raised by the Command class"""
    pass


@contextmanager
def proxy_stdf():
    """
    Circulate stdout/stderr via a proper file object. Designed to work around a
    problem where Python nose replaces sys.stdout/stderr with a custom 'Tee'
    object that is not a file object (compatible) and thus causes a crash with
    Popen.
    """
    stdout = None
    if not hasattr(sys.stdout, 'fileno'):
        stdout = sys.stdout
        sys.stdout = TemporaryFile()
    stderr = None
    if not hasattr(sys.stderr, 'fileno'):
        stderr = sys.stderr
        sys.stderr = TemporaryFile()
    try:
        yield
    finally:
        if stdout:
            sys.stdout.seek(0)
            stdout.write(sys.stdout.read())
            sys.stdout = stdout
        if stderr:
            sys.stderr.seek(0)
            stderr.write(sys.stderr.read())
            sys.stderr = stderr


class Command(object):
    """
    Wraps a shell command, so we don't have to store any kind of command
    line options in one of the git-buildpackage commands
    """
    def __init__(self, cmd, args=[], shell=False, extra_env=None, cwd=None,
                 capture_stderr=False,
                 capture_stdout=False):
        self.cmd = cmd
        self.args = args
        self.run_error = "'%s' failed: {err_reason}" % (" ".join([self.cmd] + self.args))
        self.shell = shell
        self.capture_stdout = capture_stdout
        self.capture_stderr = capture_stderr
        self.cwd = cwd
        if extra_env is not None:
            self.env = os.environ.copy()
            self.env.update(extra_env)
        else:
            self.env = None
        self._reset_state()

    def _reset_state(self):
        self.retcode = 1
        self.stdout, self.stderr, self.err_reason = [''] * 3

    def __call(self, args):
        """
        Wraps subprocess.call so we can be verbose and fix Python's
        SIGPIPE handling
        """
        def default_sigpipe():
            "Restore default signal handler (http://bugs.python.org/issue1652)"
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)

        log.debug("%s %s %s" % (self.cmd, self.args, args))
        self._reset_state()
        cmd = [self.cmd] + self.args + args
        if self.shell:
            # subprocess.call only cares about the first argument if shell=True
            cmd = " ".join(cmd)
        with proxy_stdf():
            stdout_arg = subprocess.PIPE if self.capture_stdout else sys.stdout
            stderr_arg = subprocess.PIPE if self.capture_stderr else sys.stderr
            try:
                popen = subprocess.Popen(cmd,
                                         cwd=self.cwd,
                                         shell=self.shell,
                                         env=self.env,
                                         preexec_fn=default_sigpipe,
                                         stdout=stdout_arg,
                                         stderr=stderr_arg)
                (self.stdout, self.stderr) = popen.communicate()
            except OSError as err:
                self.err_reason = "execution failed: %s" % str(err)
                self.retcode = 1
                raise

        self.retcode = popen.returncode
        if self.retcode < 0:
            self.err_reason = "it was terminated by signal %d" % -self.retcode
        elif self.retcode > 0:
            self.err_reason = "it exited with %d" % self.retcode
        return self.retcode

    def _log_err(self):
        "Log an error message"
        log.err(self._format_err())

    def _format_err(self):
        """Log an error message

        This allows to replace stdout, stderr and err_reason in
        the self.run_error.
        """
        stdout = self.stdout.rstrip() if self.stdout else self.stdout
        stderr = self.stderr.rstrip() if self.stderr else self.stderr
        stderr_or_reason = self.stderr.rstrip() if self.stderr else self.err_reason
        return self.run_error.format(stdout=stdout,
                                     stderr=stderr,
                                     stderr_or_reason=stderr_or_reason,
                                     err_reason=self.err_reason)

    def __call__(self, args=[], quiet=False):
        """Run the command and raise exception on errors

        If run quietly it will not print an error message via the
        L{gbp.log} logging API.

        Whether the command prints anything to stdout/stderr depends on
        the I{capture_stderr}, I{capture_stdout} instance variables.

        All errors will be reported as subclass of the
        L{CommandExecFailed} exception including a non zero exit
        status of the run command.

        @param args: additional command line arguments
        @type  args: C{list} of C{strings}
        @param quiet: don't log failed execution to stderr. Mostly useful during
            unit testing
        @type quiet: C{bool}

        >>> Command("/bin/true")(["foo", "bar"])
        >>> Command("/foo/bar")(quiet=True)
        Traceback (most recent call last):
        ...
        CommandExecFailed: '/foo/bar' failed: execution failed: [Errno 2] No such file or directory
        """
        try:
            ret = self.__call(args)
        except OSError:
            ret = 1
        if ret:
            if not quiet:
                self._log_err()
            raise CommandExecFailed(self._format_err())

    def call(self, args, quiet=True):
        """Like L{__call__} but let the caller handle the return status.

        Only raise L{CommandExecFailed} if we failed to launch the command
        at all (i.e. if it does not exist) not if the command returned
        nonzero.

        Logs errors using L{gbp.log} by default.

        @param args: additional command line arguments
        @type  args: C{list} of C{strings}
        @param quiet: don't log failed execution to stderr. Mostly useful during
            unit testing
        @type quiet: C{bool}
        @returns: the exit status of the run command
        @rtype: C{int}

        >>> Command("/bin/true").call(["foo", "bar"])
        0
        >>> Command("/foo/bar").call(["foo", "bar"]) # doctest:+ELLIPSIS
        Traceback (most recent call last):
        ...
        CommandExecFailed: execution failed: ...
        >>> c = Command("/bin/true", capture_stdout=True,
        ...             extra_env={'LC_ALL': 'C'})
        >>> c.call(["--version"])
        0
        >>> c.stdout.decode('utf-8').startswith('true')
        True
        >>> c = Command("/bin/false", capture_stdout=True,
        ...             extra_env={'LC_ALL': 'C'})
        >>> c.call(["--help"])
        1
        >>> c.stdout.decode('utf-8').startswith('Usage:')
        True
        """
        try:
            ret = self.__call(args)
        except OSError:
            ret = 1
            raise CommandExecFailed(self.err_reason)
        finally:
            if ret and not quiet:
                self._log_err()
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
                         ['-C', dir, compression, '-xf', archive])
        self.run_error = 'Couldn\'t unpack "%s": {err_reason}' % self.archive


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
        self.run_error = 'Couldn\'t repack "%s": {err_reason}' % self.archive


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
        Command.__init__(self, 'rm', ['-rf', tree])
        self.run_error = 'Couldn\'t remove "%s": {err_reason}' % self.tree


class Dch(Command):
    """Wrap dch and set a specific version"""
    def __init__(self, version, msg):
        args = ['-v', version]
        if msg:
            args.append(msg)
        Command.__init__(self, 'debchange', args)
        self.run_error = "Dch failed: {err_reason}"


class DpkgSourceExtract(Command):
    """
    Wrap dpkg-source to extract a Debian source package into a certain
    directory, this needs
    """
    def __init__(self):
        Command.__init__(self, 'dpkg-source', ['-x'])

    def __call__(self, dsc, output_dir):
        self.run_error = 'Couldn\'t extract "%s": {err_reason}' % dsc
        Command.__call__(self, [dsc, output_dir])


class UnpackZipArchive(Command):
    """Wrap zip to Unpack a zip file"""
    def __init__(self, archive, dir):
        self.archive = archive
        self.dir = dir

        Command.__init__(self, 'unzip', ["-q", archive, '-d', dir])
        self.run_error = 'Couldn\'t unpack "%s": {err_reason}' % self.archive


class CatenateZipArchive(Command):
    """Wrap zipmerge tool to catenate a zip file with the next"""
    def __init__(self, archive, **kwargs):
        self.archive = archive
        Command.__init__(self, 'zipmerge', [archive], **kwargs)

    def __call__(self, target):
        self.run_error = 'Couldn\'t append "%s" to "%s": {err_reason}' % \
                         (target, self.archive)
        Command.__call__(self, [target])


class GitCommand(Command):
    "Mother/Father of all git commands"
    def __init__(self, cmd, args=[], **kwargs):
        Command.__init__(self, 'git', [cmd] + args, **kwargs)
        self.run_error = "Couldn't run git %s: {err_reason}" % cmd


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
