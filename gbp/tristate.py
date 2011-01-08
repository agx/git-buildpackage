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

class Tristate(object):
    """Tri-state value: on, off or auto"""
    AUTO = -1
    ON  = True
    OFF = False
    # We accept true as alias for on and false as alias for off
    _VALID_NAMES = [ 'on', 'off', 'true', 'false', 'auto' ]

    def __init__(self, val):
        if type(val) in [ type(t) for t in (True, 1) ]:
            if val > 0:
                self._state = self.ON
            elif val < 0:
                self._state = self.AUTO
            else:
                self._state = self.OFF
        elif type(val) in [ type(t) for t in ("", u"") ]:
            if val.lower() in [ 'on', 'true' ]:
                self._state = self.ON
            elif val.lower() in [ 'auto' ]:
                self._state = self.AUTO
            else:
                self._state = self.OFF
        else:
            raise TypeError

    def __repr__(self):
        if self._state == ON:
            return "on"
        elif self._state == AUTO:
            return "auto"
        else:
            return "off"

    @classmethod
    def is_valid_state(self, stat):
        if state.lower() in self._VALID_NAMES:
            return True

    def is_auto(self):
        return [False, True][self._state == self.AUTO]

    def is_on(self):
        return [False, True][self._state == self.ON]

    def is_off(self):
        return [False, True][self._state == self.OFF]

