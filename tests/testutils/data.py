# vim: set fileencoding=utf-8 :
#
# (C) 2016 Guido Guenther <agx@sigxcpu.org>
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

from functools import wraps

import unittest


class TestCaseWithData(unittest.TestCase):
    @staticmethod
    def feed(data):
        def wrapper(fn):
            @wraps(fn)
            def feed_item(self, *args):
                for d in data:
                    try:
                        fn(self, *((d,) + args))
                    except self.failureException as e:
                        raise self.failureException(e.message + " with data %s" % repr(d))
            return feed_item
        return wrapper
