# vim: set fileencoding=utf-8 :
#
# (C) 2011,2015 Guido Guenther <agx@sigxcpu.org>
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
"""Handle Patches and Patch Series"""

import os
import re
import subprocess
import tempfile
from gbp.errors import GbpError


class Patch(object):
    """
    A patch in a L{PatchSeries}

    @ivar path: path to the patch
    @type path: string
    @ivar topic: the topic of the patch (the directory component)
    @type topic: string
    @ivar strip: path components to strip (think patch -p<strip>)
    @type strip: integer
    @ivar info: Information retrieved from a RFC822 style patch header
    @type info: C{dict} with C{str} keys and values
    @ivar long_desc: the long description of the patch
    """
    patch_exts = ['diff', 'patch']

    def __init__(self, path, topic=None, strip=None):
        self.path = path
        self.topic = topic
        self.strip = strip
        self.info = None
        self.long_desc = None

    def __repr__(self):
        repr = "<gbp.patch_series.Patch path='%s' " % self.path
        if self.topic:
            repr += "topic='%s' " % self.topic
        if self.strip is not None:
            repr += "strip=%d " % self.strip
        repr += ">"
        return repr

    def _read_info(self):
        """
        Read patch information into a structured form

        using I{git mailinfo}
        """
        self.info = {}
        body = tempfile.NamedTemporaryFile(prefix='gbp_')
        pipe = subprocess.Popen("git mailinfo '%s' /dev/null 2>/dev/null < '%s'" %
                                (body.name, self.path),
                                shell=True,
                                stdout=subprocess.PIPE).stdout
        for line in pipe:
            if ':' in line:
                rfc_header, value = line.split(" ", 1)
                header = rfc_header[:-1].lower()
                self.info[header] = value.strip()
        try:
            self.long_desc = "".join([line for line in body])
            body.close()
        except IOError as msg:
            raise GbpError("Failed to read patch header of '%s': %s" %
                           (self.patch, msg))
        finally:
            if os.path.exists(body.name):
                os.unlink(body.name)

    def _get_subject_from_filename(self):
        """
        Determine the patch's subject based on the its filename

        >>> p = Patch('debian/patches/foo.patch')
        >>> p._get_subject_from_filename()
        'foo'
        >>> Patch('foo.patch')._get_subject_from_filename()
        'foo'
        >>> Patch('debian/patches/foo.bar')._get_subject_from_filename()
        'foo.bar'
        >>> p = Patch('debian/patches/foo')
        >>> p._get_subject_from_filename()
        'foo'
        >>> Patch('0123-foo.patch')._get_subject_from_filename()
        'foo'
        >>> Patch('0123.patch')._get_subject_from_filename()
        '0123'
        >>> Patch('0123-foo-0123.patch')._get_subject_from_filename()
        'foo-0123'

        @return: the patch's subject
        @rtype: C{str}
        """
        subject = os.path.basename(self.path)
        # Strip of .diff or .patch from patch name
        try:
            base, ext = subject.rsplit('.', 1)
            if ext in self.patch_exts:
                subject = base
        except ValueError:
                pass  # No ext so keep subject as is
        return subject.lstrip('0123456789-') or subject

    def _get_info_field(self, key, get_val=None):
        """
        Return the key I{key} from the info C{dict}
        or use val if I{key} is not a valid key.

        Fill self.info if not already done.

        @param key: key to fetch
        @type key: C{str}
        @param get_val: alternate value if key is not in info dict
        @type get_val: C{str}
        """
        if self.info is None:
            self._read_info()

        if key in self.info:
            return self.info[key]
        else:
            return get_val() if get_val else None

    @property
    def subject(self):
        """
        The patch's subject, either from the patch header or from the filename.
        """
        return self._get_info_field('subject', self._get_subject_from_filename)

    @property
    def author(self):
        """The patch's author"""
        return self._get_info_field('author')

    @property
    def email(self):
        """The patch author's email address"""
        return self._get_info_field('email')

    @property
    def date(self):
        """The patch's modification time"""
        return self._get_info_field('date')


class PatchSeries(list):
    """
    A series of L{Patch}es as read from a quilt series file).
    """
    comment_re = re.compile('\s+#.*$')
    level_re = re.compile('-p(?P<level>[0-9]+)')

    @classmethod
    def read_series_file(cls, seriesfile):
        """Read a series file into L{Patch} objects"""
        patch_dir = os.path.dirname(seriesfile)

        if not os.path.exists(seriesfile):
            return []

        try:
            s = open(seriesfile)
        except Exception as err:
            raise GbpError("Cannot open series file: %s" % err)

        queue = cls._read_series(s, patch_dir)
        s.close()
        return queue

    @classmethod
    def _read_series(cls, series, patch_dir):
        """
        Read patch series

        >>> PatchSeries._read_series(['a/b',
        ...                           'a -p1 # comment',
        ...                           'a/b -p2'], '.')
        ... # doctest:+NORMALIZE_WHITESPACE
        [<gbp.patch_series.Patch path='./a/b' topic='a' >,
         <gbp.patch_series.Patch path='./a' strip=1 >,
         <gbp.patch_series.Patch path='./a/b' topic='a' strip=2 >]

        >>> PatchSeries._read_series(['# foo', 'a/b', '', '# bar'], '.')
        [<gbp.patch_series.Patch path='./a/b' topic='a' >]

        @param series: series of patches in quilt format
        @type series: iterable of strings
        @param patch_dir: path prefix to prepend to each patch path
        @type patch_dir: string
        """
        queue = PatchSeries()
        for line in series:
            try:
                if line[0] in ['\n', '#']:
                    continue
            except IndexError:
                continue  # ignore empty lines
            queue.append(cls._parse_line(line, patch_dir))
        return queue

    @staticmethod
    def _get_topic(line):
        """
        Get the topic from the patch's path

        >>> PatchSeries._get_topic("a/b c")
        'a'
        >>> PatchSeries._get_topic("asdf")
        >>> PatchSeries._get_topic("/asdf")
        """
        topic = os.path.dirname(line)
        if topic in ['', '/']:
            topic = None
        return topic

    @classmethod
    def _strip_comment(cls, line):
        """
        Strip a comment from a series file line

        >>> PatchSeries._strip_comment("does/not matter")
        'does/not matter'
        >>> PatchSeries._strip_comment("remove/the  # comment # text")
        'remove/the'
        >>> PatchSeries._strip_comment("leave/level/intact -p1 # comment # text")
        'leave/level/intact -p1'
        """
        return re.sub(cls.comment_re, '', line)

    @classmethod
    def _split_strip(cls, line):
        """
        Separate the -p<num> option from the patch name

        >>> PatchSeries._split_strip("asdf -p1")
        ('asdf', 1)
        >>> PatchSeries._split_strip("a/nice/patch")
        ('a/nice/patch', None)
        >>> PatchSeries._split_strip("asdf foo")
        ('asdf foo', None)
        """
        patch = line
        strip = None

        split = line.rsplit(None, 1)
        if len(split) > 1:
            m = cls.level_re.match(split[1])
            if m:
                patch = split[0]
                strip = int(m.group('level'))

        return (patch, strip)

    @classmethod
    def _parse_line(cls, line, patch_dir):
        """
        Parse a single line from a series file

        >>> PatchSeries._parse_line("a/b -p1", '/tmp/patches')
        <gbp.patch_series.Patch path='/tmp/patches/a/b' topic='a' strip=1 >
        >>> PatchSeries._parse_line("a/b", '.')
        <gbp.patch_series.Patch path='./a/b' topic='a' >
        """
        line = cls._strip_comment(line.rstrip())
        topic = cls._get_topic(line)
        (patch, split) = cls._split_strip(line)
        return Patch(os.path.join(patch_dir, patch), topic, split)
