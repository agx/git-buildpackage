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

from .compressor import Compressor


class Archive(object):
    # Supported archive formats
    Formats = ['tar', 'zip']

    # Map combined file extensions to archive and compression format
    Ext_aliases = {'tgz': ('tar', 'gzip'),
                   'tbz2': ('tar', 'bzip2'),
                   'tlz': ('tar', 'lzma'),
                   'txz': ('tar', 'xz')}

    @staticmethod
    def parse_filename(filename):
        """
        Given an filename return the basename (filename without the
        archive and compression extensions), archive format and
        compression method used.

        @param filename: the name of the file
        @type filename: string
        @return: tuple containing basename, archive format and compression method
        @rtype: C{tuple} of C{str}

        >>> Archive.parse_filename("abc.tar.gz")
        ('abc', 'tar', 'gzip')
        >>> Archive.parse_filename("abc.tar.bz2")
        ('abc', 'tar', 'bzip2')
        >>> Archive.parse_filename("abc.def.tbz2")
        ('abc.def', 'tar', 'bzip2')
        >>> Archive.parse_filename("abc.def.tar.xz")
        ('abc.def', 'tar', 'xz')
        >>> Archive.parse_filename("abc.zip")
        ('abc', 'zip', None)
        >>> Archive.parse_filename("abc.lzma")
        ('abc', None, 'lzma')
        >>> Archive.parse_filename("abc.tar.foo")
        ('abc.tar.foo', None, None)
        >>> Archive.parse_filename("abc")
        ('abc', None, None)
        """
        (base_name, archive_fmt, compression) = (filename, None, None)

        # Split filename into pieces
        split = filename.split(".")
        if len(split) > 1:
            if split[-1] in Archive.Ext_aliases:
                base_name = ".".join(split[:-1])
                (archive_fmt, compression) = Archive.Ext_aliases[split[-1]]
            elif split[-1] in Archive.Formats:
                base_name = ".".join(split[:-1])
                (archive_fmt, compression) = (split[-1], None)
            else:
                for (c, ext) in Compressor.Exts.items():
                    if ext == split[-1]:
                        base_name = ".".join(split[:-1])
                        compression = c
                        if len(split) > 2 and split[-2] in Archive.Formats:
                            base_name = ".".join(split[:-2])
                            archive_fmt = split[-2]

        return (base_name, archive_fmt, compression)
