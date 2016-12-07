# vim: set fileencoding=utf-8 :
#
# (C) 2014-2015 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""Test RPM changelog classes and parsing"""

from datetime import datetime
from nose.tools import assert_raises, eq_, ok_  # pylint: disable=E0611
from tempfile import NamedTemporaryFile

from gbp.rpm.changelog import _ChangelogHeader, _ChangelogEntry
from gbp.rpm.changelog import _ChangelogSection, Changelog
from gbp.rpm.changelog import ChangelogParser, ChangelogError
from gbp.rpm.policy import RpmPkgPolicy


class TestChangelogHeader(object):
    """Test the _ChangelogHeader class"""

    def test_str_format(self):
        """Basic test for header"""
        time = datetime(2014, 1, 29, 12, 13, 14)
        header = _ChangelogHeader(RpmPkgPolicy, time, name="John Doe",
                                  email="user@host.com", revision="1")
        eq_(str(header), "* Wed Jan 29 2014 John Doe <user@host.com> 1\n")

    def test_str_format_err(self):
        """Test missing properties"""
        time = datetime(2014, 1, 29, 12, 13, 14)
        header = _ChangelogHeader(RpmPkgPolicy, time, name="John", revision="1")
        with assert_raises(ChangelogError):
            str(header)

    def test_container(self):
        """Test the container methods of the class"""
        header = _ChangelogHeader(RpmPkgPolicy, datetime(2014, 1, 1), name="N",
                                  revision="1")
        # Test __getitem__()
        eq_(header['name'], "N")
        eq_(header['email'], None)
        # Test __contains__()
        ok_('name' in header)
        ok_('foo' not in header)


class TestChangelogEntry(object):
    """Test the _ChangelogEntry class"""

    def test_str_format(self):
        """Basic test"""
        entry = _ChangelogEntry(RpmPkgPolicy, author="John Doe",
                                text="- foo\n  bar")
        eq_(str(entry), "- foo\n  bar\n")


class TestChangelogSection(object):
    """Test the _ChangelogSection class"""

    def setup(self):
        """Initialize test"""
        time = datetime(2014, 1, 29, 12, 13, 14)
        self.default_sect = _ChangelogSection(RpmPkgPolicy, time, name="J. D.",
                                              email="u@h", revision="1")
        entry = _ChangelogEntry(RpmPkgPolicy, "J. D.", "- my change")
        self.default_sect.entries = [entry]

    def test_str_format(self):
        """Basic test"""
        section = self.default_sect
        eq_(str(section), "* Wed Jan 29 2014 J. D. <u@h> 1\n- my change\n\n")

    def test_append_entry(self):
        """Test add_entry() method"""
        section = self.default_sect
        entry = _ChangelogEntry(RpmPkgPolicy, author="",
                                text="- another\n  change")
        new_entry = section.append_entry(entry)
        eq_(str(section), "* Wed Jan 29 2014 J. D. <u@h> 1\n- my change\n"
                          "- another\n  change\n\n")
        eq_(new_entry, section.entries[-1])

    def test_set_header(self):
        """Test set_header() method"""
        section = self.default_sect
        time = datetime(2014, 1, 30)
        section.set_header(time=time, name="Jane", email="u@h", revision="1.1")
        eq_(str(section), "* Thu Jan 30 2014 Jane <u@h> 1.1\n- my change\n\n")


class TestChangelogParser(object):
    """Test the default changelog parser"""

    cl_default_style = """\
* Wed Jan 29 2014 Markus Lehtonen <markus.lehtonen@linux.intel.com> 0.3-1
- Version bump
- Drop foo.patch

* Tue Jan 28 2014 Markus Lehtonen <markus.lehtonen@linux.intel.com> 0.2
- Update to 0.2

* Mon Jan 27 2014 Markus Lehtonen <markus.lehtonen@linux.intel.com> 0.1
- Initial version
"""
    cl_with_authors = """\
* Wed Jan 29 2014 Markus Lehtonen <markus.lehtonen@linux.intel.com> 0.3-1
[Markus Lehtonen]
- Version bump
[John Doe]
- Bug fix
"""
    # Invalid timestamp / name
    cl_broken_header_1 = """\
* Wed Jan 29 2014Markus Lehtonen <markus.lehtonen@linux.intel.com> 0.3-1
- Version bump
"""
    # Whitespace before the asterisk in the header
    cl_broken_header_2 = """\
 * Wed Jan 29 2014 Markus Lehtonen <markus.lehtonen@linux.intel.com> 0.3-1
- Version bump
"""
    # Invalid timestamp
    cl_broken_header_3 = """\
* Wed Jan 32 2014 Markus Lehtonen <markus.lehtonen@linux.intel.com> 0.3-1
- Version bump
"""
    # Missing email
    cl_broken_header_4 = """\
* Wed Jan 29 2014 Markus Lehtonen 0.3-1
- Version bump
"""
    # Garbage before section header
    cl_broken_header_5 = """\
---garbage---
* Wed Jan 29 2014 Markus Lehtonen <markus.lehtonen@linux.intel.com> 0.3-1
- Version bump
"""

    parser = ChangelogParser(RpmPkgPolicy)

    def test_parse_changelog(self):
        """Basic tests for successful parsing"""
        # Raw parsing of changelog
        changelog = self.parser.raw_parse_string(self.cl_default_style)
        eq_(len(changelog.sections), 3)

        # Check that re-creating the changelog doesn't mangle it
        eq_(str(changelog), self.cl_default_style)

        # Parse and check section
        section = self.parser.parse_section(changelog.sections[0])

        eq_(section.header['time'], datetime(2014, 1, 29))
        eq_(section.header['name'], "Markus Lehtonen")
        eq_(section.header['email'], "markus.lehtonen@linux.intel.com")
        eq_(section.header['revision'], "0.3-1")

        # Check that re-creating section doesn't mangle it
        eq_(str(section), changelog.sections[0])

    def test_parse_authors(self):
        """Test parsing of authors from changelog entries"""
        section = self.parser.parse_section(self.cl_with_authors)
        eq_(section.entries[0].author, "Markus Lehtonen")
        eq_(section.entries[1].author, "John Doe")

    def test_parse_changelog_file(self):
        """Basic tests for parsing a file"""
        # Create file and parse it
        tmpfile = NamedTemporaryFile()
        tmpfile.write(self.cl_default_style)
        tmpfile.file.flush()
        changelog = self.parser.raw_parse_file(tmpfile.name)
        # Check parsing results
        eq_(len(changelog.sections), 3)
        eq_(str(changelog), self.cl_default_style)
        # Cleanup
        tmpfile.close()

    def test_parse_section_fail(self):
        """Basic tests for failures of changelog section parsing"""
        with assert_raises(ChangelogError):
            self.parser.parse_section(self.cl_broken_header_1)

        with assert_raises(ChangelogError):
            self.parser.parse_section(self.cl_broken_header_2)

        with assert_raises(ChangelogError):
            self.parser.parse_section(self.cl_broken_header_3)

        with assert_raises(ChangelogError):
            self.parser.parse_section(self.cl_broken_header_4)

    def test_parse_changelog_fail(self):
        """Basic tests for changelog parsing failures"""
        with assert_raises(ChangelogError):
            self.parser.raw_parse_string(self.cl_broken_header_5)


class TestChangelog(object):
    """Unit tests for the Changelog class"""

    def basic_test(self):
        """Test basic initialization"""
        changelog = Changelog(RpmPkgPolicy)
        eq_(str(changelog), "")

    def test_add_section(self):
        """Test the add_section() method"""
        changelog = Changelog(RpmPkgPolicy)
        time = datetime(2014, 1, 30)
        new_section = changelog.add_section(time=time, name="Jane Doe",
                                            email="j@doe.com", revision="1.2")
        eq_(str(changelog), "* Thu Jan 30 2014 Jane Doe <j@doe.com> 1.2\n\n")
        eq_(new_section, changelog.sections[0])
