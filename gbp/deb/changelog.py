# vim: set fileencoding=utf-8 :
#
# (C) 2011 Guido Günther <agx@sigxcpu.org>
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
"""A Debian Changelog"""

import email
import os
import subprocess
from gbp.command_wrappers import Command


class NoChangeLogError(Exception):
    """No changelog found"""
    pass


class ParseChangeLogError(Exception):
    """Problem parsing changelog"""
    pass


class ChangeLogSection(object):
    """A section in the changelog describing one particular version"""
    def __init__(self, package, version):
        self._package = package
        self._version = version

    @property
    def package(self):
        return self._package

    @property
    def version(self):
        return self._version

    @classmethod
    def parse(cls, section):
        """
        Parse one changelog section

        @param section: a changelog section
        @type section: C{str}
        @returns: the parse changelog section
        @rtype: L{ChangeLogSection}
        """
        header = section.split('\n')[0]
        package = header.split()[0]
        version = header.split()[1][1:-1]
        return cls(package, version)


class ChangeLog(object):
    """A Debian changelog"""

    def __init__(self, contents=None, filename=None):
        """
        @param contents: the contents of the changelog
        @type contents: C{str}
        @param filename: the filename of the changelog
        @param filename: C{str}
        """
        self._contents = ''
        self._cp = None
        self._filename = filename

        # Check that either contents or filename is passed (but not both)
        if (not filename and not contents) or (filename and contents):
            raise ValueError("Either filename or contents must be passed")

        if filename and not os.access(filename, os.F_OK):
            raise NoChangeLogError("Changelog %s not found" % (filename, ))

        if contents:
            self._contents = contents[:]
        else:
            self._read()
        self._parse()

    def _run_parsechangelog(self, options=None):
        options = options if options is not None else []
        cmd = subprocess.Popen(['dpkg-parsechangelog', '-l-'] + options,
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        (stdout, stderr) = cmd.communicate(self._contents.encode('utf-8'))
        if cmd.returncode:
            raise ParseChangeLogError("Failed to parse changelog. "
                                      "dpkg-parsechangelog said:\n%s" % stderr.decode().strip())
        return stdout.decode()

    def _parse(self):
        """Parse a changelog based on the already read contents."""
        output = self._run_parsechangelog()
        # Parse the result of dpkg-parsechangelog (which looks like
        # email headers)
        cp = email.message_from_string(output)
        try:
            if ':' in cp['Version']:
                cp['Epoch'], cp['NoEpoch-Version'] = cp['Version'].split(':', 1)
            else:
                cp['NoEpoch-Version'] = cp['Version']
            if '-' in cp['NoEpoch-Version']:
                cp['Upstream-Version'], cp['Debian-Version'] = cp['NoEpoch-Version'].rsplit('-', 1)
            else:
                cp['Debian-Version'] = cp['NoEpoch-Version']

            # py3's email.message_from_string() saves dpkg-parsechangelog's
            # first newline from the "Changes" field.
            changes = cp['Changes'].lstrip("\n")
            del cp['Changes']
            cp['Changes'] = changes
        except TypeError:
            raise ParseChangeLogError(output.split('\n')[0])

        self._cp = cp

    def _read(self):
        with open(self.filename, encoding='utf-8') as f:
            self._contents = f.read()

    def __getitem__(self, item):
        return self._cp[item]

    def __setitem__(self, item, value):
        self._cp[item] = value

    @property
    def filename(self):
        """The filename (path) of the changelog"""
        return self._filename

    @property
    def name(self):
        """The packages name"""
        return self._cp['Source']

    @property
    def version(self):
        """The full version string"""
        return self._cp['Version']

    @property
    def distribution(self):
        return self._cp['Distribution']

    @property
    def upstream_version(self):
        """The upstream version"""
        return self._cp['Upstream-Version']

    @property
    def debian_version(self):
        """The Debian part of the version number"""
        return self._cp['Debian-Version']

    @property
    def epoch(self):
        """The package's epoch"""
        return self._cp['Epoch']

    @property
    def noepoch(self):
        """The version string without the epoch"""
        return self._cp['NoEpoch-Version']

    def has_epoch(self):
        """
        Whether the version has an epoch

        @return: C{True} if the version has an epoch, C{False} otherwise
        @rtype: C{bool}
        """
        return 'Epoch' in self._cp

    @property
    def author(self):
        """
        The author of the last modification
        """

        return self._parse_maint(self._cp['Maintainer'])[0]

    @property
    def email(self):
        """
        The author's email
        """
        return self._parse_maint(self._cp['Maintainer'])[1]

    @property
    def date(self):
        """
        The date of the last modification as rfc822 date
        """
        return self._cp['Date']

    @property
    def sections_iter(self):
        """
        Iterate over sections in the changelog
        """
        section = ''
        for line in self._contents.split('\n'):
            if line and line[0] not in [' ', '\t']:
                section += line
            else:
                if section:
                    yield ChangeLogSection.parse(section)
                    section = ''

    @property
    def sections(self):
        """
        Get sections in the changelog
        """
        return list(self.sections_iter)

    @staticmethod
    def spawn_dch(msg=[], author=None, email=None, newversion=False, version=None,
                  release=False, distribution=None, dch_options=None):
        """
        Spawn dch

        @param author: committers name
        @type author: C{str}
        @param email: committers email
        @type email: C{str}
        @param newversion: start a new version
        @type newversion: C{bool}
        @param version: the verion to use
        @type version: C{str}
        @param release: finalize changelog for releaze
        @type release: C{bool}
        @param distribution: distribution to use
        @type distribution: C{str}
        @param dch_options: options passed verbatim to dch
        @type dch_options: C{list}
        """
        env = {}
        args = ['--no-auto-nmu']
        if newversion:
            if version:
                try:
                    args.append(version['increment'])
                except KeyError:
                    args.append('--newversion=%s' % version['version'])
            else:
                args.append('-i')
        elif release:
            args.extend(["--release", "--no-force-save-on-release"])
            msg = None

        if author:
            env['DEBFULLNAME'] = author.encode('utf-8')
        if email:
            env['DEBEMAIL'] = email.encode('utf-8')

        if distribution:
            args.append("--distribution=%s" % distribution)

        args.extend(dch_options or [])

        if '--create' in args:
            env['EDITOR'] = env['VISUAL'] = '/bin/true'

        args.append('--')
        if msg:
            args.append('[[[insert-git-dch-commit-message-here]]]')
        else:
            args.append('')
        dch = Command('debchange', args, extra_env=env, capture_stderr=True)
        dch.run_error = Command._f("Dch failed: {stderr_or_reason}")
        dch([], quiet=True)
        if msg:
            old_cl = open("debian/changelog", "r", encoding='utf-8')
            new_cl = open("debian/changelog.bak", "w", encoding='utf-8')
            for line in old_cl:
                if line == "  * [[[insert-git-dch-commit-message-here]]]\n":
                    print("  * " + msg[0], file=new_cl)
                    for line in msg[1:]:
                        print("    " + line, file=new_cl)
                else:
                    print(line, end='', file=new_cl)
            os.rename("debian/changelog.bak", "debian/changelog")

    def add_entry(self, msg, author=None, email=None, dch_options=[]):
        """Add a single changelog entry

        @param msg: log message to add
        @type msg: C{str}
        @param author: name of the author of the log message
        @type author: C{str}
        @param email: email of the author of the log message
        @type email: C{str}
        @param dch_options: options passed verbatim to dch
        @type dch_options: C{list}
        """
        self.spawn_dch(msg=msg, author=author, email=email, dch_options=dch_options)

    def add_section(self, msg, distribution, author=None, email=None,
                    version={}, dch_options=[]):
        """Add a new section to the changelog

        @param msg: log message to add
        @type msg: C{str}
        @param distribution: distribution to set for the new changelog entry
        @type distribution: C{str}
        @param author: name of the author of the log message
        @type author: C{str}
        @param email: email of the author of the log message
        @type email: C{str}
        @param version: version to set for the new changelog entry
        @param version: C{dict}
        @param dch_options: options passed verbatim to dch
        @type dch_options: C{list}
        """
        self.spawn_dch(msg=msg, newversion=True, version=version, author=author,
                       email=email, distribution=distribution, dch_options=dch_options)

    def get_changes(self, since='0~'):
        return self._run_parsechangelog(['-v%s' % since, '-SChanges'])

    @staticmethod
    def _parse_maint(maintainer):
        """
        Parse maintainer

        Mostly rfc822 but we allow for commas
        """
        def _quote(u):
            return u.replace(',', '##comma##')

        def _unquote(q):
            return q.replace('##comma##', ',')

        name, mail = email.utils.parseaddr(_quote(maintainer or ''))
        return (_unquote(name), _unquote(mail))

    @classmethod
    def create(cls, package=None, version=None):
        """
        Create a new, empty changelog
        """
        dch_options = ['--create']
        if package:
            dch_options.extend(['--package', package])
        if version:
            dch_options.extend(['--newversion', version])

        cls.spawn_dch(dch_options=dch_options)
        return cls(filename='debian/changelog')
