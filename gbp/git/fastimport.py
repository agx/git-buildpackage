
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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Git fast import class"""

import subprocess
from gbp.errors import GbpError

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
        except OSError as err:
            raise GbpError("Error spawning git fast-import: %s" % err)
        except ValueError as err:
            raise GbpError("Invalid argument when spawning git fast-import: %s" % err)

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


