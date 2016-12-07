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
"""Simple implementation of a doubly linked list"""

import collections

import gbp.log


class LinkedListNode(object):
    """Node of the linked list"""

    def __init__(self, data="", prev_node=None, next_node=None):
        self.prev = prev_node
        self.next = next_node
        self._data = data

    def __str__(self):
        return str(self.data)

    @property
    def data(self):
        """Get data stored into node"""
        if self._data is None:
            gbp.log.debug("BUG: referencing a deleted node!")
            return("")
        return self._data

    def set_data(self, data):
        """
        Set data stored into node

        >>> node = LinkedListNode('foo')
        >>> node.data
        'foo'
        >>> node.set_data('bar')
        >>> node.data
        'bar'
        >>> node.set_data(None)
        >>> node.data
        ''
        """
        if data is None:
            gbp.log.debug("BUG: trying to store 'None', not allowed")
            data = ""
        self._data = data

    def delete(self):
        """Delete node"""
        if self.prev:
            self.prev.next = self.next
        if self.next:
            self.next.prev = self.prev
        self._data = None


class LinkedListIterator(collections.Iterator):
    """Iterator for the linked list"""

    def __init__(self, obj):
        self._next = obj.first

    def __next__(self):
        ret = self._next
        if ret:
            self._next = ret.next
        else:
            raise StopIteration
        return ret

    def next(self):
        return self.__next__()


class LinkedList(collections.Iterable):
    """Doubly linked list"""

    def __init__(self):
        self._first = None
        self._last = None

    def __iter__(self):
        return LinkedListIterator(self)

    def __len__(self):
        for num, data in enumerate(self):
            pass
        return num + 1

    @property
    def first(self):
        """Get the first node of the list"""
        return self._first

    def prepend(self, data):
        """
        Insert to the beginning of list

        >>> list = LinkedList()
        >>> [str(data) for data in list]
        []
        >>> node = list.prepend("foo")
        >>> len(list)
        1
        >>> node = list.prepend("bar")
        >>> [str(data) for data in list]
        ['bar', 'foo']
        """
        if self._first is None:
            new = self._first = self._last = LinkedListNode(data)
        else:
            new = self.insert_before(self._first, data)
        return new

    def append(self, data):
        """
        Insert to the end of list

        >>> list = LinkedList()
        >>> node = list.append('foo')
        >>> len(list)
        1
        >>> node = list.append('bar')
        >>> [str(data) for data in list]
        ['foo', 'bar']
        """
        if self._last is None:
            return self.prepend(data)
        else:
            return self.insert_after(self._last, data)

    def insert_before(self, node, data=""):
        """
        Insert before a node

        >>> list = LinkedList()
        >>> node1 = list.append('foo')
        >>> node2 = list.insert_before(node1, 'bar')
        >>> node3 = list.insert_before(node1, 'baz')
        >>> [str(data) for data in list]
        ['bar', 'baz', 'foo']
        """
        new = LinkedListNode(data, prev_node=node.prev, next_node=node)
        if node.prev:
            node.prev.next = new
        else:
            self._first = new
        node.prev = new
        return new

    def insert_after(self, node, data=""):
        """
        Insert after a node

        >>> list = LinkedList()
        >>> node1 = list.prepend('foo')
        >>> node2 = list.insert_after(node1, 'bar')
        >>> node3 = list.insert_after(node1, 'baz')
        >>> [str(data) for data in list]
        ['foo', 'baz', 'bar']
        """
        new = LinkedListNode(data, prev_node=node, next_node=node.next)
        if node.next:
            node.next.prev = new
        else:
            self._last = new
        node.next = new
        return new

    def delete(self, node):
        """
        Delete node

        >>> list = LinkedList()
        >>> node1 = list.prepend('foo')
        >>> node2 = list.insert_after(node1, 'bar')
        >>> node3 = list.insert_before(node2, 'baz')
        >>> [str(data) for data in list]
        ['foo', 'baz', 'bar']
        >>> str(list.delete(node3))
        'foo'
        >>> [str(data) for data in list]
        ['foo', 'bar']
        >>> print("%s" % node3)
        <BLANKLINE>
        >>> str(list.delete(node1))
        'bar'
        >>> [str(data) for data in list]
        ['bar']
        >>> list.delete(node2)
        >>> [str(data) for data in list]
        []
        """
        ret = node.prev
        if node is self._first:
            ret = self._first = self._first.next
        if node is self._last:
            self._last = self._last.prev
        node.delete()
        return ret

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
