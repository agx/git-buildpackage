# (C) 2015 Jonathan Toppins <jtoppins@cumulusnetworks.com>
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
"""Test gbp.dch.extract_bts_cmds()"""

import unittest

from gbp.dch import extract_bts_cmds


class OptionsStub:
    def __init__(self):
        self.meta_closes = "Closes|LP"
        self.meta_closes_bugnum = r'(?:bug|issue)?\#?\s?\d+'


class TestExtractBTSCmds(unittest.TestCase):
    def test_debian_commands(self):
        """Test default BTS command extraction that is applicable to Debian"""
        options = OptionsStub()
        lines = """This is a test commit

Closes: bug#12345
Closes: 456
"""
        bugs, dummy = extract_bts_cmds(lines.split('\n'), options)
        self.assertEquals(bugs, {'Closes': ['bug#12345', '456']})

    def test_nondebian_commands(self):
        """Test non-default BTS commands. We use the example given in the
        documentation manpages."""
        options = OptionsStub()
        options.meta_closes_bugnum = "(?:bug)?\s*ex-\d+"
        lines = """This is a test commit
some more lines...

Closes: bug EX-12345
Closes: ex-01273
Closes: bug ex-1ab
Closes: EX--12345
"""
        bugs, dummy = extract_bts_cmds(lines.split('\n'), options)
        self.assertEquals(bugs, {'Closes': ['bug EX-12345', 'ex-01273',
                                            'bug ex-1']})
