# vim: set fileencoding=utf-8 :
#
# (C) 2007, 2008, 2009, 2010, 2013 Guido Günther <agx@sigxcpu.org>
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
#
"""Generate RPM changelog entries from git commit messages"""

from datetime import datetime
import os.path
import pwd
import re
import sys
import socket

import gbp.command_wrappers as gbpc
import gbp.log
from gbp.config import GbpConfArgParserRpm
from gbp.errors import GbpError
from gbp.rpm import (guess_spec, NoSpecError, SpecFile, split_version_str,
                     compose_version_str)
from gbp.rpm.changelog import Changelog, ChangelogParser, ChangelogError
from gbp.rpm.git import GitRepositoryError, RpmGitRepository
from gbp.rpm.policy import RpmPkgPolicy
from gbp.scripts.common import ExitCodes
from gbp.tmpfile import init_tmpdir, del_tmpdir


ChangelogEntryFormatter = RpmPkgPolicy.ChangelogEntryFormatter


class ChangelogFile(object):
    """Container for changelog file, whether it be a standalone changelog
       or a spec file"""

    def __init__(self, file_path):
        parser = ChangelogParser(RpmPkgPolicy)

        if os.path.splitext(file_path)[1] == '.spec':
            gbp.log.debug("Using spec file '%s' as changelog" % file_path)
            self._file = SpecFile(file_path)
            self.changelog = parser.raw_parse_string(self._file.get_changelog())
        else:
            self._file = os.path.abspath(file_path)
            if not os.path.exists(file_path):
                gbp.log.info("Changelog '%s' not found, creating new "
                             "changelog file" % file_path)
                self.changelog = Changelog(RpmPkgPolicy)
            else:
                gbp.log.debug("Using changelog file '%s'" % file_path)
                self.changelog = parser.raw_parse_file(self._file)

        # Parse topmost section and try to determine the start commit
        if self.changelog.sections:
            self.changelog.sections[0] = parser.parse_section(
                self.changelog.sections[0])

    def write(self):
        """Write changelog file to disk"""
        if isinstance(self._file, SpecFile):
            self._file.set_changelog(str(self.changelog))
            self._file.write_spec_file()
        else:
            with open(self._file, 'w') as fobj:
                fobj.write(str(self.changelog))

    @property
    def path(self):
        """File path"""
        if isinstance(self._file, SpecFile):
            return self._file.specpath
        else:
            return self._file


def load_customizations(customization_file):
    """Load user defined customizations file"""
    # Load customization file
    if not customization_file:
        return
    customizations = {}
    try:
        with open(customization_file) as f:
            exec(f.read(), customizations, customizations)
    except Exception as err:
        raise GbpError("Failed to load customization file: %s" % err)

    # Set customization classes / functions
    global ChangelogEntryFormatter
    if 'ChangelogEntryFormatter' in customizations:
        ChangelogEntryFormatter = customizations.get('ChangelogEntryFormatter')


def determine_editor(options):
    """Determine text editor"""

    # Check if we need to spawn an editor
    states = ['always']
    if options.release:
        states.append('release')
    if options.spawn_editor not in states:
        return None

    # Determine the correct editor
    if options.editor_cmd:
        return options.editor_cmd
    elif 'EDITOR' in os.environ:
        return os.environ['EDITOR']
    else:
        return 'vi'


def check_branch(repo, options):
    """Check the current git branch"""
    try:
        branch = repo.get_branch()
    except GitRepositoryError:
        branch = None
    if options.packaging_branch != branch and not options.ignore_branch:
        gbp.log.err("You are not on branch '%s' but on '%s'" %
                    (options.packaging_branch, branch))
        raise GbpError("Use --ignore-branch to ignore or "
                       "--packaging-branch to set the branch name.")


def parse_spec_file(repo, options):
    """Find and parse spec file"""
    if options.spec_file:
        spec_path = os.path.join(repo.path, options.spec_file)
        spec = SpecFile(spec_path)
    else:
        spec = guess_spec(os.path.join(repo.path, options.packaging_dir),
                          True, os.path.basename(repo.path) + '.spec')
    options.packaging_dir = spec.specdir
    return spec


def parse_changelog_file(repo, spec, options):
    """Find and parse changelog file"""
    changes_file_name = os.path.splitext(spec.specfile)[0] + '.changes'
    changes_file_path = os.path.join(options.packaging_dir, changes_file_name)

    # Determine changelog file path
    if options.changelog_file == "SPEC":
        changelog_path = spec.specpath
    elif options.changelog_file == "CHANGES":
        changelog_path = changes_file_path
    elif options.changelog_file == 'auto':
        if os.path.exists(changes_file_path):
            changelog_path = changes_file_path
        else:
            changelog_path = spec.specpath
    else:
        changelog_path = os.path.join(repo.path, options.changelog_file)

    return ChangelogFile(changelog_path)


def guess_commit(section, repo, options):
    """Guess the last commit documented in a changelog header"""

    if not section:
        return None
    header = section.header

    # Try to parse the fields from the header revision
    rev_re = '^%s$' % re.sub(r'%\((\S+?)\)s', r'(?P<\1>\S+)',
                             options.changelog_revision)
    match = re.match(rev_re, header['revision'], re.I)
    fields = match.groupdict() if match else {}

    # First, try to find tag-name, if present
    if 'tagname' in fields:
        gbp.log.debug("Trying to find tagname %s" % fields['tagname'])
        try:
            return repo.rev_parse("%s^0" % fields['tagname'])
        except GitRepositoryError:
            gbp.log.warn("Changelog points to tagname '%s' which is not found "
                         "in the git repository" % fields['tagname'])

    # Next, try to find packaging tag matching the version
    tag_str_fields = {'vendor': options.vendor}
    if 'version' in fields:
        gbp.log.debug("Trying to find packaging tag for version '%s'" %
                      fields['version'])
        full_version = fields['version']
        tag_str_fields.update(split_version_str(full_version))
    elif 'upstreamversion' in fields:
        gbp.log.debug("Trying to find packaging tag for version '%s'" %
                      fields['upstreamversion'])
        tag_str_fields['upstreamversion'] = fields['upstreamversion']
        if 'release' in fields:
            tag_str_fields['release'] = fields['release']
    commit = repo.find_version(options.packaging_tag,
                               tag_str_fields)
    if commit:
        return commit
    else:
        gbp.log.info("Couldn't find packaging tag for version %s" %
                     header['revision'])

    # As a last resort we look at the timestamp
    timestamp = header['time'].isoformat()
    last = repo.get_commits(num=1, options="--until='%s'" % timestamp)
    if last:
        gbp.log.info("Using commit (%s) before the last changelog timestamp "
                     "(%s)" % (last, timestamp))
        return last[0]
    return None


def get_start_commit(changelog, repo, options):
    """Get the start commit from which to generate new entries"""
    if options.since:
        since = options.since
    else:
        if changelog.sections:
            since = guess_commit(changelog.sections[0], repo, options)
        else:
            since = None
        if not since:
            raise GbpError("Couldn't determine starting point from "
                           "changelog, please use the '--since' option")
        gbp.log.info("Continuing from commit '%s'" % since)
    return since


def get_author(repo, use_git_config):
    """Get author and email from git configuration"""
    author = email = None

    if use_git_config:
        modifier = repo.get_author_info()
        author = modifier.name
        email = modifier.email

    passwd_data = pwd.getpwuid(os.getuid())
    if not author:
        # On some distros (Ubuntu, at least) the gecos field has it's own
        # internal structure of comma-separated fields
        author = passwd_data.pw_gecos.split(',')[0].strip()
        if not author:
            author = passwd_data.pw_name
    if not email:
        if 'EMAIL' in os.environ:
            email = os.environ['EMAIL']
        else:
            email = "%s@%s" % (passwd_data.pw_name, socket.getfqdn())

    return author, email


def entries_from_commits(changelog, repo, commits, options):
    """Generate a list of formatted changelog entries from a list of commits"""
    entries = []
    for commit in commits:
        info = repo.get_commit_info(commit)
        entry_text = ChangelogEntryFormatter.compose(info, full=options.full,
                                                     ignore_re=options.ignore_regex,
                                                     id_len=options.idlen)
        if entry_text:
            entries.append(changelog.create_entry(author=info['author'].name,
                                                  text=entry_text))
    return entries


def update_changelog(changelog, entries, repo, spec, options):
    """Update the changelog with a range of commits"""
    # Get info for section header
    now = datetime.now()
    name, email = get_author(repo, options.git_author)
    rev_str_fields = dict(spec.version,
                          version=compose_version_str(spec.version),
                          vendor=options.vendor,
                          tagname=repo.describe('HEAD', longfmt=True,
                                                always=True))
    try:
        revision = options.changelog_revision % rev_str_fields
    except KeyError as err:
        raise GbpError("Unable to construct revision field: unknown key "
                       "%s, only %s are accepted" % (err, rev_str_fields.keys()))

    # Add a new changelog section if new release or an empty changelog
    if options.release or not changelog.sections:
        top_section = changelog.add_section(time=now, name=name,
                                            email=email, revision=revision)
    else:
        # Re-use already parsed top section
        top_section = changelog.sections[0]
        top_section.set_header(time=now, name=name,
                               email=email, revision=revision)

    # Add new entries to the topmost section
    for entry in entries:
        top_section.append_entry(entry)


def build_parser(name):
    """Construct command line parser"""
    try:
        parser = GbpConfArgParserRpm.create_parser(prog=name)
    except GbpError as err:
        gbp.log.err(err)
        return None

    range_grp = parser.add_argument_group("commit range options",
                                          "which commits to add to the changelog")
    format_grp = parser.add_argument_group("changelog entry formatting",
                                           "how to format the changelog entries")
    naming_grp = parser.add_argument_group("naming",
                                           "branch names, tag formats, directory and file naming")

    # Non-grouped options
    parser.add_arg("-v", "--verbose", action="store_true",
                   help="verbose command execution")
    parser.add_conf_file_arg("--color",
                             type='tristate')
    parser.add_conf_file_arg("--color-scheme")
    parser.add_conf_file_arg("--tmp-dir")
    parser.add_conf_file_arg("--vendor", action="store")
    parser.add_conf_file_arg("--git-log",
                             help="options to pass to git-log")
    parser.add_bool_conf_file_arg("--ignore-branch")
    parser.add_conf_file_arg("--customizations",
                             dest="customization_file",
                             help="Load Python code from CUSTOMIZATION_FILE. At the "
                             "moment, the only useful thing the code can do is define a "
                             "custom ChangelogEntryFormatter class.")

    # Naming group options
    naming_grp.add_conf_file_arg("--packaging-branch")
    naming_grp.add_conf_file_arg("--packaging-tag")
    naming_grp.add_conf_file_arg("--packaging-dir")
    naming_grp.add_conf_file_arg("--changelog-file")
    naming_grp.add_conf_file_arg("--spec-file")
    # Range group options
    range_grp.add_arg("-s", "--since",
                      help="commit to start from (e.g. HEAD^^^, release/0.1.2)")
    # Formatting group options
    format_grp.add_arg("--no-release", action="store_false",
                       dest="release",
                       help="no release, just update the last changelog section")
    format_grp.add_bool_conf_file_arg("--git-author")
    format_grp.add_bool_conf_file_arg("--full")
    format_grp.add_conf_file_arg("--id-length", dest="idlen",
                                 help="include N digits of the commit id in "
                                 "the changelog entry",
                                 type=int, metavar="N")
    format_grp.add_conf_file_arg("--ignore-regex",
                                 help="Ignore lines in commit message matching regex,")
    format_grp.add_conf_file_arg("--changelog-revision")
    format_grp.add_conf_file_arg("--spawn-editor")
    format_grp.add_conf_file_arg("--editor-cmd")

    parser.add_argument("path", metavar="PATH", nargs="*",
                        help="path(s) to look for changes")
    return parser


def parse_args(argv):
    """Parse command line and config file options"""
    parser = build_parser(os.path.basename(argv[0]))
    if not parser:
        return None

    options = parser.parse_args(argv[1:])

    if not options.changelog_revision:
        options.changelog_revision = RpmPkgPolicy.Changelog.header_rev_format

    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    return options


def main(argv):
    """Script main function"""
    options = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    try:
        init_tmpdir(options.tmp_dir, prefix='rpm-ch_')

        load_customizations(options.customization_file)
        editor_cmd = determine_editor(options)

        repo = RpmGitRepository('.')
        check_branch(repo, options)

        # Find and parse spec file
        spec = parse_spec_file(repo, options)

        # Find and parse changelog file
        ch_file = parse_changelog_file(repo, spec, options)
        since = get_start_commit(ch_file.changelog, repo, options)

        # Get range of commits from where to generate changes
        if options.path:
            gbp.log.info("Only looking for changes in '%s'" % ", ".join(options.path))
        commits = repo.get_commits(since=since, until='HEAD', paths=options.path,
                                   options=options.git_log.split(" "))
        commits.reverse()
        if not commits:
            gbp.log.info("No changes detected from %s to %s." % (since, 'HEAD'))

        # Do the actual update
        entries = entries_from_commits(ch_file.changelog, repo, commits,
                                       options)
        update_changelog(ch_file.changelog, entries, repo, spec, options)

        # Write to file
        ch_file.write()

        if editor_cmd:
            gbpc.Command(editor_cmd, [ch_file.path])()

    except (GbpError, GitRepositoryError, ChangelogError, NoSpecError) as err:
        if len(err.__str__()):
            gbp.log.err(err)
        return 1
    except KeyboardInterrupt:
        gbp.log.err("Interrupted. Aborting.")
        return 1
    finally:
        del_tmpdir()

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
