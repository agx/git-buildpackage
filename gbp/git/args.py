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
"""
Git command argument handling helpers
"""

import six
import collections


class GitArgs(object):
    """
    Handle arguments to git commands

    >>> GitArgs('-h', '--no-foo').args
    ['-h', '--no-foo']
    >>> GitArgs('-n', 123).args
    ['-n', '123']
    >>> GitArgs().add('--more-foo', '--less-bar').args
    ['--more-foo', '--less-bar']
    >>> GitArgs().add(['--foo', '--bar']).args
    ['--foo', '--bar']
    >>> GitArgs().add_cond(1 > 2, '--opt', '--no-opt').args
    ['--no-opt']
    >>> GitArgs().add_true(True, '--true').args
    ['--true']
    >>> GitArgs().add_false(True, '--true').args
    []
    >>> GitArgs().add_false(False, '--false').args
    ['--false']
    """

    def __init__(self, *args):
        self._args = []
        self.add(args)

    @property
    def args(self):
        return self._args

    def add(self, *args):
        """
        Add arguments to argument list
        """
        for arg in args:
            if isinstance(arg, six.string_types):
                self._args.append(arg)
            elif isinstance(arg, collections.Iterable):
                for i in iter(arg):
                    self._args.append(str(i))
            else:
                self._args.append(str(arg))

        return self

    def add_true(self, condition, *args):
        """
        Add I{args} if I{condition} is C{True}

        @param condition: the condition to test
        @type condition: C{bool}
        @param args: arguments to add
        """
        if condition:
            self.add(*args)
        return self

    def add_false(self, condition, *args):
        """
        Add I{args} if I{condition} is C{False}

        @param condition: the condition to test
        @type condition: C{bool}
        @param args: arguments to add
        """
        self.add_true(not condition, *args)
        return self

    def add_cond(self, condition, opt, noopt=[]):
        """
        Add option I{opt} to I{alist} if I{condition} is C{True}
        else add I{noopt}.

        @param condition: condition
        @type condition: C{bool}
        @param opt: option to add if I{condition} is C{True}
        @type opt: C{str} or C{list}
        @param noopt: option to add if I{condition} is C{False}
        @type noopt: C{str} or C{list}
        """
        if condition:
            self.add(opt)
        else:
            self.add(noopt)
        return self
