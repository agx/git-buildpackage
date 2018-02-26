# vim: set fileencoding=utf-8 :
#
# (C) 2014 Guido Günther <agx@sigxcpu.org>
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
"""Format a message"""

from gbp.errors import GbpError


def format_str(msg, args):
    """
    Format a string with the given dict. Be a bit more verbose than
    default python about the error cause.

    >>> format_str("%(foo)", {})
    Traceback (most recent call last):
    ...
    gbp.errors.GbpError: Failed to format %(foo): Missing value 'foo' in {}
    >>> format_str("%(foo)", {'foo': 'bar'})
    Traceback (most recent call last):
    ...
    gbp.errors.GbpError: Failed to format %(foo) with {'foo': 'bar'}: incomplete format
    >>> format_str("A %(foo)s is a %(bar)s", {'foo': 'dog', 'bar': 'mamal'})
    'A dog is a mamal'
    """
    try:
        return msg % args
    except ValueError as e:
        raise GbpError("Failed to format %s with %s: %s" % (msg, args, e))
    except KeyError as e:
        raise GbpError("Failed to format %s: Missing value %s in %s" %
                       (msg, e, args))


def format_b(fmtstr, *args):
    """String-like interpolation for bytes objects.

    NOTE: This is a compatibility wrapper for older versions (<3.5) of Python 3
    which do not support the percent operator ('%') for bytes objects. This
    function should be removed (and replaced by simple '%') when Python 3.5
    has gained wide enough adoption.

    >>> format_b(b'%s %d', b'foo', 123)
    b'foo 123'
    >>> format_b(b'foo 123')
    b'foo 123'
    >>> format_b('%s %d', b'foo', 123)
    Traceback (most recent call last):
    ...
    AttributeError: 'str' object has no attribute 'decode'
    """
    fmtstr = fmtstr.decode()
    strargs = tuple([(a.decode() if isinstance(a, bytes) else a) for a in args])
    return (fmtstr % strargs).encode()
