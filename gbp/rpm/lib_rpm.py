# vim: set fileencoding=utf-8 :
#
# (C) 2012 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""Wrapper module for librpm"""

import tempfile

import gbp.log
from gbp.rpm.policy import RpmPkgPolicy

try:
    # Try to load special RPM lib to be used for GBP (only)
    librpm = __import__(RpmPkgPolicy.python_rpmlib_module_name)
except ImportError:
    gbp.log.warn("Failed to import '%s' as rpm python module, using host's "
                 "default rpm library instead" %
                 RpmPkgPolicy.python_rpmlib_module_name)
    import rpm as librpm

# Module initialization
_rpmlog = tempfile.NamedTemporaryFile(prefix='gbp_rpmlog')
_rpmlogfd = _rpmlog.file
librpm.setVerbosity(librpm.RPMLOG_INFO)
librpm.setLogFile(_rpmlogfd)


def get_librpm_log(truncate=True):
    """Get rpmlib log output"""
    _rpmlogfd.seek(0)
    log = [line.strip() for line in _rpmlogfd.readlines()]
    if truncate:
        _rpmlogfd.truncate(0)
    return log
