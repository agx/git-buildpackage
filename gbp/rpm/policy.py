# vim: set fileencoding=utf-8 :
#
# (C) 2012 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""Default packaging policy for RPM"""

import re

from gbp.pkg import PkgPolicy, parse_archive_filename
from gbp.scripts.common.pq import parse_gbp_commands


class RpmPkgPolicy(PkgPolicy):
    """Packaging policy for RPM"""

    # Special rpmlib python module for GBP (only)
    python_rpmlib_module_name = "rpm"

    alnum = 'a-zA-Z0-9'
    # Valid characters for RPM pkg name
    name_whitelist_chars = '._+%{}\-'
    # Valid characters for RPM pkg version
    version_whitelist_chars = '._+%{}~'

    # Regexp for checking the validity of package name
    packagename_re = re.compile("^[%s][%s%s]+$" %
                                (alnum, alnum, name_whitelist_chars))
    packagename_msg = ("Package names must be at least two characters long, "
                       "start with an alphanumeric and can only contain "
                       "alphanumerics or characters in %s" %
                       list(name_whitelist_chars))

    # Regexp for checking the validity of package (upstream) version
    upstreamversion_re = re.compile("^[0-9][%s%s]*$" %
                                    (alnum, version_whitelist_chars))
    upstreamversion_msg = ("Upstream version numbers must start with a digit "
                           "and can only containg alphanumerics or characters "
                           "in %s" % list(version_whitelist_chars))

    @classmethod
    def is_valid_orig_archive(cls, filename):
        """
        Is this a valid orig source archive

        @param filename: upstream source archive filename
        @type filename: C{str}
        @return: true if valid upstream source archive filename
        @rtype: C{bool}

        >>> RpmPkgPolicy.is_valid_orig_archive("foo/bar_baz.tar.gz")
        True
        >>> RpmPkgPolicy.is_valid_orig_archive("foo.bar.tar")
        True
        >>> RpmPkgPolicy.is_valid_orig_archive("foo.bar")
        False
        >>> RpmPkgPolicy.is_valid_orig_archive("foo.gz")
        False
        """
        _base, arch_fmt, _compression = parse_archive_filename(filename)
        if arch_fmt:
            return True
        return False

    class Changelog(object):
        """Container for changelog related policy settings"""

        # Regexps for splitting/parsing the changelog section (of
        # Tizen / Fedora style changelogs)
        section_match_re = r'^\*'
        section_split_re = r'^\*\s*(?P<ch_header>\S.*?)$\n(?P<ch_body>.*)'
        header_split_re = r'(?P<ch_time>\S.*\s[0-9]{4})\s+(?P<ch_name>\S.*$)'
        header_name_split_re = r'(?P<name>[^<]*)\s+<(?P<email>[^>]+)>((\s*-)?\s+(?P<revision>\S+))?$'
        body_name_re = r'\[(?P<name>.*)\]'

        # Changelog header format (when writing out changelog)
        header_format = "* %(time)s %(name)s <%(email)s> %(revision)s"
        header_time_format = "%a %b %d %Y"
        header_rev_format = "%(version)s"

    class ChangelogEntryFormatter(object):
        """Helper class for generating changelog entries from git commits"""

        # Maximum length for a changelog entry line
        max_entry_line_length = 76
        # Bug tracking system related meta tags recognized from git commit msg
        bts_meta_tags = ("Close", "Closes", "Fixes", "Fix")
        # Regexp for matching bug tracking system ids (e.g. "bgo#123")
        bug_id_re = r'[A-Za-z0-9#_\-]+'

        @classmethod
        def _parse_bts_tags(cls, lines, meta_tags):
            """
            Parse and filter out bug tracking system related meta tags from
            commit message.

            @param lines: commit message
            @type lines: C{list} of C{str}
            @param meta_tags: meta tags to look for
            @type meta_tags: C{tuple} of C{str}
            @return: bts-ids per meta tag and the non-mathced lines
            @rtype: (C{dict}, C{list} of C{str})
            """
            tags = {}
            other_lines = []
            bts_re = re.compile(r'^(?P<tag>%s):\s*(?P<ids>.*)' %
                                ('|'.join(meta_tags)), re.I)
            bug_id_re = re.compile(cls.bug_id_re)
            for line in lines:
                match = bts_re.match(line)
                if match:
                    tag = match.group('tag')
                    ids_str = match.group('ids')
                    bug_ids = [bug_id.strip() for bug_id in
                               bug_id_re.findall(ids_str)]
                    if tag in tags:
                        tags[tag] += bug_ids
                    else:
                        tags[tag] = bug_ids
                else:
                    other_lines.append(line)
            return (tags, other_lines)

        @classmethod
        def _extra_filter(cls, lines, ignore_re):
            """
            Filter out specific lines from the commit message.

            @param lines: commit message
            @type lines: C{list} of C{str}
            @param ignore_re: regexp for matching ignored lines
            @type ignore_re: C{str}
            @return: filtered commit message
            @rtype: C{list} of C{str}
            """
            if ignore_re:
                match = re.compile(ignore_re)
                return [line for line in lines if not match.match(line)]
            else:
                return lines

        @classmethod
        def compose(cls, commit_info, **kwargs):
            """
            Generate a changelog entry from a git commit.

            @param commit_info: info about the commit
            @type commit_info: C{commit_info} object from
                L{gbp.git.repository.GitRepository.get_commit_info()}.
            @param kwargs: additional arguments to the compose() method,
                currently we recognize 'full', 'id_len' and 'ignore_re'
            @type kwargs: C{dict}
            @return: formatted changelog entry
            @rtype: C{list} of C{str}
            """
            # Parse and filter out gbp command meta-tags
            cmds, body = parse_gbp_commands(commit_info, 'gbp-rpm-ch',
                                            ('ignore', 'short', 'full'), ())
            body = body.splitlines()
            if 'ignore' in cmds:
                return None

            # Parse and filter out bts-related meta-tags
            bts_tags, body = cls._parse_bts_tags(body, cls.bts_meta_tags)

            # Additional filtering
            body = cls._extra_filter(body, kwargs['ignore_re'])

            # Generate changelog entry
            subject = commit_info['subject']
            commitid = commit_info['id']
            if kwargs['id_len']:
                text = ["- [%s] %s" % (commitid[0:kwargs['id_len']], subject)]
            else:
                text = ["- %s" % subject]

            # Add all non-filtered-out lines from commit message, unless 'short'
            if (kwargs['full'] or 'full' in cmds) and 'short' not in cmds:
                # Add all non-blank body lines.
                text.extend(["  " + line for line in body if line.strip()])

            # Add bts tags and ids in the end
            for tag, ids in bts_tags.iteritems():
                bts_msg = " (%s: %s)" % (tag, ', '.join(ids))
                if len(text[-1]) + len(bts_msg) >= cls.max_entry_line_length:
                    text.append(" ")
                text[-1] += bts_msg

            return text
