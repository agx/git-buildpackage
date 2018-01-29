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


class Compressor(object):
    # Map frequently used names of compression types to the internal ones:
    Aliases = {'bz2': 'bzip2',
               'gz': 'gzip', }

    Opts = {'gzip': '-n',
            'bzip2': '',
            'lzma': '',
            'xz': ''}

    ParallelOpts = {'lzma': '-T0',
                    'xz': '-T0'}

    Exts = {'gzip': 'gz',
            'bzip2': 'bz2',
            'lzma': 'lzma',
            'xz': 'xz'}

    def __init__(self, type_, level=None, parallel=False):
        self._type = type_
        self._level = int(level) if level not in [None, ''] else None
        self._more_opts = self.Opts.get(self._type, '')
        self._parallel = parallel
        if parallel:
            self._more_opts += self.ParallelOpts.get(self._type, '')

    def is_known(self):
        return self.type in self.Opts.keys()

    @property
    def type(self):
        return self._type

    @property
    def level(self):
        return self._level

    @property
    def parallel(self):
        return self._parallel

    @property
    def _level_opt(self):
        return '-%d' % self.level if self.level is not None else ''

    def cmdline(self, stdout=True):
        """
        >>> Compressor('gzip', level=9).cmdline()
        'gzip -9 -n -c'
        >>> Compressor('gzip').cmdline(True)
        'gzip  -n -c'
        """
        return "%s %s %s %s" % (self.type, self._level_opt, self._more_opts,
                                "-c" if stdout else '')

    def __repr__(self):
        """
        >>> Compressor('gzip').__repr__()
        "<compressor type='gzip'>"
        >>> Compressor('gzip', 9).__repr__()
        "<compressor type='gzip' level=9>"
        >>> Compressor('xz', 9, True).__repr__()
        "<compressor type='xz' level=9 parallel=True>"
        """
        opts_str = " level=%s" % self.level if self.level is not None else ""
        opts_str += " parallel=True" if self.parallel else ""
        return "<compressor type='%s'%s>" % (self.type, opts_str)
