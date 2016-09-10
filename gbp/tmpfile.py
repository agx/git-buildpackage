# vim: set fileencoding=utf-8 :
#
# (C) 2012, 2015 Intel Corporation <markus.lehtonen@linux.intel.com>
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
#
"""Temporary directory handling"""

import os
import shutil
import tempfile

from gbp.errors import GbpError


_old_tempdirs = []


def init_tmpdir(path, prefix):
    """Initialize a temporary directory structure"""
    try:
        if not os.path.exists(path):
            os.makedirs(path)
    except OSError as err:
        raise GbpError("Unable to create tmpdir %s (%s)" % (path, err))

    tmpdir = tempfile.mkdtemp(dir=path, prefix=prefix)

    # Set newly created dir as the default value for all further tempfile
    # calls
    _old_tempdirs.append(tempfile.tempdir)
    tempfile.tempdir = tmpdir
    return tmpdir


def del_tmpdir():
    """Remove tempdir and restore tempfile module"""
    if _old_tempdirs:
        if os.path.exists(tempfile.tempdir) and \
                not os.getenv('GBP_TMPFILE_NOCLEAN'):
            shutil.rmtree(tempfile.tempdir)
        tempfile.tempdir = _old_tempdirs.pop()

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
