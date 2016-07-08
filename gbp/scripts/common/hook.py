# vim: set fileencoding=utf-8 :
#
# (C) 2016 Guido Günther <agx@sigxcpu.org>
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
"""Common code for runniing hooks"""

from gbp.command_wrappers import RunAtCommand


class Hook(RunAtCommand):
    "A hook run by one of the scripts"
    def __init__(self, name, cmd, extra_env):
        RunAtCommand.__init__(self, cmd, shell=True, extra_env=extra_env)
        self.run_error = '%s-hook %s' % (name, self.run_error)

    @staticmethod
    def md(a, b):
        "Merge two dictionaires a and b into a new one"
        c = a.copy()
        c.update(b)
        return c
