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

import os
import re
from errors import GbpError

class Patch(object):
    """
    A patch in a patchqueue

    @ivar path: path to the patch
    @type path: string
    @ivar topic: the topic of the patch
    @type topic: string
    @ivar strip: path components to strip (think patch -p<strip>)
    @type strip: integer
    """
    def __init__(self, path, topic=None, strip=None):
        self.path = path
        self.topic = topic
        self.strip = strip

    def __repr__(self):
        repr = "<gbp.pq.Patch path='%s' " % self.path
        if self.topic:
                repr += "topic='%s' " % self.topic
        if self.strip != None:
                repr += "strip=%d " % self.strip
        repr += ">"
        return repr


class PatchQueue(list):
    @classmethod
    def read_series_file(klass, seriesfile):
        """Read a series file into gbp.pq.Patch objects"""
        patch_dir = os.path.dirname(seriesfile)
        try:
            s = file(seriesfile)
        except Exception, err:
            raise GbpError("Cannot open series file: %s" % err)

        queue = klass._read_series(s, patch_dir)
        s.close()
        return queue

    @classmethod
    def _read_series(klass, series, patch_dir):
        """
        Read patch series
        @param series: series of patches in quilt format
        @type series: iterable of strings
        @param patch_dir: path prefix to prepend to each patch path
        @type patch_dir: string

        >>> PatchQueue._read_series(['a/b', \
                            'a -p1', \
                            'a/b -p2'], '.') # doctest:+NORMALIZE_WHITESPACE
        [<gbp.pq.Patch path='./a/b' topic='a' >,
         <gbp.pq.Patch path='./a' strip=1 >,
         <gbp.pq.Patch path='./a/b' topic='a' strip=2 >]
        """

        queue = PatchQueue()
        for line in series:
            queue.append(klass._parse_line(line, patch_dir))
        return queue

    @staticmethod
    def _get_topic(line):
        """
        Get the topic from the path's path
        >>> PatchQueue._get_topic("a/b c")
        'a'
        >>> PatchQueue._get_topic("asdf")
        >>> PatchQueue._get_topic("/asdf")
        """
        topic = os.path.dirname(line)
        if topic in [ '', '/' ]:
            topic = None
        return topic

    @staticmethod
    def _split_strip(line):
        """
        Separate the -p<num> option from the patch name

        >>> PatchQueue._split_strip("asdf -p1")
        ('asdf', 1)
        >>> PatchQueue._split_strip("a/nice/patch")
        ('a/nice/patch', None)
        >>> PatchQueue._split_strip("asdf foo")
        ('asdf foo', None)
        """
        patch = line
        strip = None

        split = line.rsplit(None, 1)
        if len(split) > 1:
            m = re.match('-p(?P<level>[0-9]+)', split[1])
            if m:
                patch = split[0]
                strip = int(m.group('level'))

        return (patch, strip)

    @classmethod
    def _parse_line(klass, line, patch_dir):
        """
        Parse a single line from a patch file

        >>> PatchQueue._parse_line("a/b -p1", '/tmp/patches')
        <gbp.pq.Patch path='/tmp/patches/a/b' topic='a' strip=1 >
        >>> PatchQueue._parse_line("a/b", '.')
        <gbp.pq.Patch path='./a/b' topic='a' >
        """
        line = line.rstrip()
        topic = klass._get_topic(line)
        (patch, split) = klass._split_strip(line)
        return Patch(os.path.join(patch_dir, patch), topic, split)


