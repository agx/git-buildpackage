# vim: set fileencoding=utf-8 :
#
# (C) 2014 Guido Guenther <agx@sigxcpu.org>
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
"""Format a message"""

from gbp.errors import GbpError

def format_msg(msg, args):
    """
    Format a strin with the given dict. Be a bit more verbose than
    default python about the error cause.

    >>> format_msg("%(foo)", {})
    Traceback (most recent call last):
    ...
    GbpError: Failed to format %(foo): Missing value 'foo' in {}
    >>> format_msg("%(foo)", {'foo': 'bar'})
    Traceback (most recent call last):
    ...
    GbpError: Failed to format %(foo) with {'foo': 'bar'}: incomplete format
    >>> format_msg("A %(foo)s is a %(bar)s", {'foo': 'dog', 'bar': 'mamal'})
    'A dog is a mamal'
    """
    try:
        return msg % args
    except ValueError as e:
        raise GbpError("Failed to format %s with %s: %s" % (msg, args, e))
    except KeyError as e:
            raise GbpError("Failed to format %s: Missing value %s in %s" % (msg, e, args))


