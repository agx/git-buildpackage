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
#    along with this program; if not, please see
#    <http://www.gnu.org/licenses/>

"""
A switch with three states: on|off|auto
"""


class Tristate(object):
    """Tri-state value: on, off or auto """
    ON = True       # state is on == do it
    OFF = False     # state is off == don't do it
    AUTO = -1       # autodetect == do if possible

    # We accept true as alias for on and false as alias for off
    _VALID_NAMES = ['on', 'off', 'true', 'false', 'auto']

    def __init__(self, val):
        if type(val) in [type(t) for t in (True, 1)]:
            if val > 0:
                self._state = self.ON
            elif val < 0:
                self._state = self.AUTO
            else:
                self._state = self.OFF
        elif type(val) in [type(t) for t in ("", u"")]:
            if val.lower() in ['on', 'true']:
                self._state = self.ON
            elif val.lower() in ['auto']:
                self._state = self.AUTO
            else:
                self._state = self.OFF
        elif type(val) is Tristate:
            self._state = val.state
        else:
            raise TypeError

    def __repr__(self):
        """
        >>> Tristate('on').__repr__()
        'on'
        >>> Tristate(True).__repr__()
        'on'
        >>> Tristate(False).__repr__()
        'off'
        >>> Tristate('auto').__repr__()
        'auto'
        """
        if self._state == self.ON:
            return 'on'
        elif self._state == self.AUTO:
            return 'auto'
        else:
            return 'off'

    def __nonzero__(self):
        """
        >>> Tristate('on').__nonzero__()
        True
        >>> Tristate('auto').__nonzero__()
        True
        >>> Tristate('off').__nonzero__()
        False
        """
        return self._state is not self.OFF

    @property
    def state(self):
        """Get current state"""
        return self._state

    def is_auto(self):
        return [False, True][self._state == self.AUTO]

    def is_on(self):
        return [False, True][self._state == self.ON]

    def is_off(self):
        return [False, True][self._state == self.OFF]

    def do(self, function, *args, **kwargs):
        """
        Run function if tristate is on or auto, only report a failure if
        tristate is on since failing is o.k. for autodetect.
        """
        if self.is_off():
            return True

        success = function(*args, **kwargs)
        if not success:
            return [True, False][self.is_on()]

        return True
