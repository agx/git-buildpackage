# vim: set fileencoding=utf-8 :
#
# (C) 2017 Guido Guenther <agx@sigxcpu.org>
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
"Helpers to handle paths"


def to_bin(path):
    """Convert to binary if not already

    We want paths to be binary since we can't assume an encoding but
    it shall still be convenient to pass in unicode strings
    """
    return path.encode() if not isinstance(path, bytes) else path
