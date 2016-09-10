
# vim: set fileencoding=utf-8 :
#
# (C) 2011 Guido Guenther <agx@sigxcpu.org>
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
"""Git fast import class"""

import subprocess
import time
from gbp.errors import GbpError


class FastImport(object):
    """Add data to a git repository using I{git fast-import}"""
    _bufsize = 1024

    m_regular = 644
    m_exec = 755
    m_symlink = 120000

    def __init__(self, repo):
        """
        @param repo: the git repository L{FastImport} acts on
        @type repo: L{GitRepository}
        """
        self._repo = repo
        try:
            self._fi = subprocess.Popen(['git', 'fast-import', '--quiet'],
                                        stdin=subprocess.PIPE, cwd=repo.path)
            self._out = self._fi.stdin
        except OSError as err:
            raise GbpError("Error spawning git fast-import: %s" % err)
        except ValueError as err:
            raise GbpError(
                "Invalid argument when spawning git fast-import: %s" % err)

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

    def add_file(self, filename, fd, size, mode=m_regular):
        """
        Add a file

        @param filename: the name of the file to add
        @type filename: C{str}
        @param fd: stream to read data from
        @type fd: C{File} like object
        @param size: size of the file to add
        @type size: C{int}
        @param mode: file mode, default is L{FastImport.m_regular}.
        @type mode: C{int}
        """
        self._do_file(filename, mode, fd, size)

    def add_symlink(self, linkname, linktarget):
        """
        Add a symlink

        @param linkname: the symbolic link's name
        @param linkname: C{str}
        @param linktarget: the target the symlink points to
        @type linktarget: C{str}
        """
        self._out.write("M %d inline %s\n" % (self.m_symlink, linkname))
        self._out.write("data %s\n" % len(linktarget))
        self._out.write("%s\n" % linktarget)

    def start_commit(self, branch, committer, msg):
        """
        Start a fast import commit

        @param branch: branch to commit on
        @type branch: C{str}
        @param committer: the committer information
        @type committer: L{GitModifier}
        @param msg: the commit message
        @type msg: C{str}
        """
        length = len(msg)
        if not committer.date:
            committer.date = "%d %s" % (time.time(),
                                        time.strftime("%z"))

        if self._repo.has_branch(branch):
            from_ = "from refs/heads/%(branch)s^0\n"
        else:
            from_ = ''

        self._out.write("""commit refs/heads/%(branch)s
committer %(name)s <%(email)s> %(time)s
data %(length)s
%(msg)s%(from)s""" %
                        {'branch': branch,
                         'name': committer.name,
                         'email': committer.email,
                         'time': committer.date,
                         'length': length,
                         'msg': msg,
                         'from': from_,
                         })

    def deleteall(self):
        """
        Issue I{deleteall} to fastimport so we start from a empty tree
        """
        self._out.write("deleteall\n")

    def close(self):
        """
        Close fast-import issuing all pending actions
        """
        if self._out:
            self._out.close()
        if self._fi:
            self._fi.wait()

    def __del__(self):
        self.close()
