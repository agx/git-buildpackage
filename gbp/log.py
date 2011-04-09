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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""Simple colored logging classes"""

import os
import sys
import gbp.tristate

logger = None

class Logger(object):

    DEBUG, INFO, WARNING, ERROR = range(4)

    COLOR_NONE = 0
    COLOR_BLACK, COLOR_RED, COLOR_GREEN = range(30,33)

    COLOR_SEQ = "\033[%dm"
    BOLD_SEQ = "\033[1m"


    format = ("%(color)s"
              "gbp:%(levelname)s: "
              "%(message)s"
              "%(coloroff)s")

    def __init__(self):
        self.levels = { self.DEBUG:   [ 'debug', self.COLOR_GREEN ],
                        self.INFO:    [ 'info',  self.COLOR_GREEN ],
                        self.WARNING: [ 'warn',  self.COLOR_RED   ],
                        self.ERROR:   [ 'error', self.COLOR_RED   ], }
        self.color = False
        self.level = self.INFO
        self.get_color = self.get_coloroff = self._color_dummy

    def set_level(self, level):
        self.level = level

    def _is_tty(self):
        if (os.getenv("EMACS") and
            os.getenv("INSIDE_EMACS", "").endswith(",comint")):
            return False

        if (sys.stderr.isatty() and
            sys.stdout.isatty()):
            return True

        return False

    def set_color(self, color):
        if type(color) == type(True):
            self.color = color
        else:
            if color.is_on():
                self.color = True
            elif color.is_auto():
                self.color = self._is_tty()
            else:
                self.color = False

        if self.color:
            self.get_color = self._color
            self.get_coloroff = self._color_off
        else:
            self.get_color = self.get_coloroff = self._color_dummy

    def _color_dummy(self, level=None):
        return ""

    def _color(self, level):
        return self.COLOR_SEQ % (self.levels[level][1])

    def _color_off(self):
        return self.COLOR_SEQ % self.COLOR_NONE


    def log(self, level, message):
        if level < self.level:
            return

        out = [sys.stdout, sys.stderr][level >= self.WARNING]
        print >>out, self.format % { 'levelname': self.levels[level][0],
                                     'color': self.get_color(level),
                                     'message': message,
                                     'coloroff': self.get_coloroff()}


def err(msg):
    logger.log(Logger.ERROR, msg)

def warn(msg):
    logger.log(Logger.WARNING, msg)

def info(msg):
    logger.log(Logger.INFO, msg)

def debug(msg):
    logger.log(Logger.DEBUG, msg)

def setup(color, verbose):
    logger.set_color(color)
    if verbose:
        logger.set_level(Logger.DEBUG)

if not logger:
    logger = Logger()

