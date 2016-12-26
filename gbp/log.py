# vim: set fileencoding=utf-8 :
#
# (C) 2010 Guido Guenther <agx@sigxcpu.org>
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
#
"""Simple colored logging classes"""

import os
import sys
import logging
from logging import (DEBUG, INFO, WARNING, ERROR, CRITICAL, getLogger)
import gbp.tristate


COLORS = dict([('none', 0)] + list(zip(['black', 'red', 'green', 'yellow', 'blue',
                                        'magenta', 'cyan', 'white'], range(30, 38))))
DEFAULT_COLOR_SCHEME = {DEBUG: COLORS['green'],
                        INFO: COLORS['green'],
                        WARNING: COLORS['red'],
                        ERROR: COLORS['red'],
                        CRITICAL: COLORS['red']}


class GbpFilter(object):
    """Filter for enabling selective output"""
    def __init__(self, levels):
        self._levels = levels

    def filter(self, record):
        """Do we show the record"""
        if record.levelno in self._levels:
            return True
        return False


class GbpStreamHandler(logging.StreamHandler):
    """Special stream handler for enabling colored output"""

    COLOR_SEQ = "\033[%dm"
    OFF_SEQ = "\033[0m"

    def __init__(self, stream=None, color='auto'):
        super(GbpStreamHandler, self).__init__(stream)
        self._color = gbp.tristate.Tristate(color)
        self._color_scheme = DEFAULT_COLOR_SCHEME.copy()
        msg_fmt = "%(color)s%(name)s:%(levelname)s: %(message)s%(coloroff)s"
        self.setFormatter(logging.Formatter(fmt=msg_fmt))

    def set_color(self, color):
        """Set/unset colorized output"""
        self._color = gbp.tristate.Tristate(color)

    def set_color_scheme(self, color_scheme={}):
        """Set logging colors"""
        self._color_scheme = DEFAULT_COLOR_SCHEME.copy()
        self._color_scheme.update(color_scheme)

    def set_format(self, fmt):
        """Set logging format"""
        self.setFormatter(logging.Formatter(fmt=fmt))

    def _use_color(self):
        """Check if to print in color or not"""
        if self._color.is_on():
            return True
        elif self._color.is_auto() and hasattr(self.stream, 'isatty'):
            in_emacs = (os.getenv("EMACS") and
                        os.getenv("INSIDE_EMACS", "").endswith(",comint"))
            return self.stream.isatty() and not in_emacs
        return False

    def format(self, record):
        """Colorizing formatter"""
        record.color = record.coloroff = ""
        if self._use_color():
            record.color = self.COLOR_SEQ % self._color_scheme[record.levelno]
            record.coloroff = self.OFF_SEQ
        record.levelname = record.levelname.lower()
        return super(GbpStreamHandler, self).format(record)


class GbpLogger(logging.Logger):
    """Logger class for git-buildpackage"""

    def __init__(self, name, color='auto', *args, **kwargs):
        super(GbpLogger, self).__init__(name, *args, **kwargs)
        self._default_handlers = [GbpStreamHandler(sys.stdout, color),
                                  GbpStreamHandler(sys.stderr, color)]
        self._default_handlers[0].addFilter(GbpFilter([DEBUG, INFO]))
        self._default_handlers[1].addFilter(GbpFilter([WARNING, ERROR,
                                                       CRITICAL]))
        for hdlr in self._default_handlers:
            self.addHandler(hdlr)

    def set_color(self, color):
        """Set/unset colorized output of the default handlers"""
        for hdlr in self._default_handlers:
            hdlr.set_color(color)

    def set_color_scheme(self, color_scheme={}):
        """Set the color scheme of the default handlers"""
        for hdlr in self._default_handlers:
            hdlr.set_color_scheme(color_scheme)

    def set_format(self, fmt):
        """Set the format of the default handlers"""
        for hdlr in self._default_handlers:
            hdlr.set_format(fmt)


def err(msg):
    """Logs a message with level ERROR on the GBP logger"""
    LOGGER.error(msg)


def warn(msg):
    """Logs a message with level WARNING on the GBP logger"""
    LOGGER.warning(msg)


def info(msg):
    """Logs a message with level INFO on the GBP logger"""
    LOGGER.info(msg)


def debug(msg):
    """Logs a message with level DEBUG on the GBP logger"""
    LOGGER.debug(msg)


def _parse_color_scheme(color_scheme=""):
    """Set logging colors"""
    scheme = {}
    colors = color_scheme.split(':')
    levels = (DEBUG, INFO, WARNING, ERROR)

    if color_scheme and len(colors) != len(levels):
        raise ValueError("Number color fields in color scheme not %d'"
                         % len(levels))

    for field, color in enumerate(colors):
        level = levels[field]
        try:
            scheme[level] = int(color)
        except ValueError:
            try:
                scheme[level] = COLORS[color.lower()]
            except KeyError:
                pass
    return scheme


def setup(color, verbose, color_scheme=""):
    """Basic logger setup"""
    LOGGER.set_color(color)
    LOGGER.set_color_scheme(_parse_color_scheme(color_scheme))
    if verbose:
        LOGGER.setLevel(DEBUG)
    else:
        LOGGER.setLevel(INFO)


# Initialize the module
logging.setLoggerClass(GbpLogger)

LOGGER = getLogger("gbp")
