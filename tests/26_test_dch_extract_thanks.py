# vim: set fileencoding=utf-8 :
#
# (C) 2015 Jonathan Toppins <jtoppins@cumulusnetworks.com>
# (C) 2016 Guido Günther <agx@sigxcpu.org>
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
"""Test gbp.dch.extract_thanks_info()"""

import unittest

from gbp.dch import extract_thanks_info


class OptionsStub:
    def __init__(self):
        self.meta_closes = "Closes|LP"
        self.meta_closes_bugnum = r'(?:bug|issue)?\#?\s?\d+'


class TestExtractThanks(unittest.TestCase):
    def test_debian_commands(self):
        """Test default thanks extraction"""
        lines = """
thAnks: a lot
Thanks: everyone"""

        lines += "   \n"  # Add some trailing whitespace
        bugs, dummy = extract_thanks_info(lines.split('\n'), None)
        self.assertEquals(bugs, ['a lot', 'everyone'])
