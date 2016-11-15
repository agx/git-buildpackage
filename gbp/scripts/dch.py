# vim: set fileencoding=utf-8 :
#
# (C) 2007, 2008, 2009, 2010, 2013, 2015 Guido Guenther <agx@sigxcpu.org>
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
"""Generate Debian changelog entries from Git commit messages"""

from __future__ import print_function

import os.path
import re
import sys
import shutil
import gbp.command_wrappers as gbpc
import gbp.dch as dch
import gbp.log
from gbp.config import GbpOptionParserDebian, GbpOptionGroup
from gbp.errors import GbpError
from gbp.deb import compare_versions
from gbp.deb.source import DebianSource, DebianSourceError
from gbp.deb.git import GitRepositoryError, DebianGitRepository
from gbp.deb.changelog import ChangeLog, NoChangeLogError
from gbp.scripts.common import ExitCodes

user_customizations = {}
snapshot_re = re.compile("\s*\*\* SNAPSHOT build @(?P<commit>[a-z0-9]+)\s+\*\*")


def guess_version_from_upstream(repo, upstream_tag_format, upstream_branch, cp):
    """
    Guess the version based on the latest version on the upstream branch.
    If the version in dch is already higher this function returns None.
    """
    try:
        version = repo.debian_version_from_upstream(upstream_tag_format,
                                                    upstream_branch,
                                                    epoch=cp.epoch,
                                                    debian_release=False)
        gbp.log.debug("Found upstream version %s." % version)
        if compare_versions(version, cp.version) > 0:
            return "%s-1" % version
    except GitRepositoryError as e:
        gbp.log.debug("No upstream tag found: %s" % e)
    return None


def get_author_email(repo, use_git_config):
    """Get author and email from git configuration"""
    author = email = None

    if use_git_config:
        try:
            author = repo.get_config('user.name')
        except KeyError:
            pass

        try:
            email = repo.get_config('user.email')
        except KeyError:
            pass
    return author, email


def fixup_section(repo, use_git_author, options, dch_options):
    """
    Fixup the changelog header and trailer's committer and email address

    It might otherwise point to the last git committer instead of the person
    creating the changelog

    This also applies --distribution and --urgency options passed to gbp dch
    """
    author, email = get_author_email(repo, use_git_author)
    used_options = ['distribution', 'urgency']
    opts = []
    mainttrailer_opts = ['--nomainttrailer', '--mainttrailer', '-t']

    # This must not be done for snapshots or snapshots changelog entries
    # will not be concatenated
    if not options.snapshot:
        for opt in used_options:
            val = getattr(options, opt)
            if val:
                gbp.log.debug("Set header option '%s' to '%s'" % (opt, val))
                opts.append("--%s=%s" % (opt, val))
    else:
        gbp.log.debug("Snapshot enabled: do not fixup options in header")

    if use_git_author:
        for opt in mainttrailer_opts:
            if opt in dch_options:
                break
        else:
            opts.append(mainttrailer_opts[0])
    ChangeLog.spawn_dch(msg='', author=author, email=email, dch_options=dch_options + opts)


def snapshot_version(version):
    """
    Get the current release and snapshot version.

    Format is <debian-version>~<release>.gbp<short-commit-id>

    >>> snapshot_version('1.0-1')
    ('1.0-1', 0)
    >>> snapshot_version('1.0-1~1.test0')
    ('1.0-1~1.test0', 0)
    >>> snapshot_version('1.0-1~2.gbp1234')
    ('1.0-1', 2)
    """
    try:
        (release, suffix) = version.rsplit('~', 1)
        (snapshot, commit) = suffix.split('.', 1)
        if not commit.startswith('gbp'):
            raise ValueError
        else:
            snapshot = int(snapshot)
    except ValueError:  # not a snapshot release
        release = version
        snapshot = 0
    return release, snapshot


def mangle_changelog(changelog, cp, snapshot=''):
    """
    Mangle changelog to either add or remove snapshot markers

    @param snapshot: SHA1 if snapshot header should be added/maintained,
        empty if it should be removed
    @type  snapshot: C{str}
    """
    try:
        tmpfile = '%s.%s' % (changelog, snapshot)
        cw = open(tmpfile, 'w')
        cr = open(changelog, 'r')

        print("%(Source)s (%(MangledVersion)s) "
              "%(Distribution)s; urgency=%(urgency)s\n" % cp, file=cw)

        cr.readline()  # skip version and empty line
        cr.readline()
        line = cr.readline()
        if snapshot_re.match(line):
            cr.readline()  # consume the empty line after the snapshot header
            line = ''

        if snapshot:
            print("  ** SNAPSHOT build @%s **\n" % snapshot, file=cw)

        if line:
            print(line.rstrip(), file=cw)
        shutil.copyfileobj(cr, cw)
        cw.close()
        cr.close()
        os.unlink(changelog)
        os.rename(tmpfile, changelog)
    except OSError as e:
        raise GbpError("Error mangling changelog %s" % e)


def do_release(changelog, repo, cp, use_git_author, dch_options):
    """Remove the snapshot header and set the distribution"""
    author, email = get_author_email(repo, use_git_author)
    (release, snapshot) = snapshot_version(cp['Version'])
    if snapshot:
        cp['MangledVersion'] = release
        mangle_changelog(changelog, cp)
    cp.spawn_dch(release=True, author=author, email=email, dch_options=dch_options)


def do_snapshot(changelog, repo, next_snapshot):
    """
    Add new snapshot banner to most recent changelog section.
    The next snapshot number is calculated by eval()'ing next_snapshot.
    """
    commit = repo.head

    cp = ChangeLog(filename=changelog)
    (release, snapshot) = snapshot_version(cp['Version'])
    snapshot = int(eval(next_snapshot))

    suffix = "%d.gbp%s" % (snapshot, "".join(commit[0:6]))
    cp['MangledVersion'] = "%s~%s" % (release, suffix)

    mangle_changelog(changelog, cp, commit)
    return snapshot, commit, cp['MangledVersion']


def parse_commit(repo, commitid, opts, last_commit=False):
    """Parse a commit and return message, author, and author email"""
    commit_info = repo.get_commit_info(commitid)
    author = commit_info['author'].name
    email = commit_info['author'].email
    format_entry = user_customizations.get('format_changelog_entry')
    if not format_entry:
        format_entry = dch.format_changelog_entry
    entry = format_entry(commit_info, opts, last_commit=last_commit)
    return entry, (author, email)


def guess_documented_commit(cp, repo, tagformat):
    """
    Guess the last commit documented in the changelog from the snapshot banner,
    the last tagged version or the last point the changelog was touched.

    @param cp: the changelog
    @param repo: the git repository
    @param tagformat: the format for Debian tags
    @returns: the commit that was last documented in the changelog
    @rtype: C{str}
    @raises GbpError: In case we fail to find a commit to start at
    """
    # Check for snapshot banner
    sr = re.search(snapshot_re, cp['Changes'])
    if sr:
        return sr.group('commit')

    # Check if the latest version in the changelog is already tagged. If
    # so this is the last documented commit.
    commit = repo.find_version(tagformat, cp.version)
    if commit:
        gbp.log.info("Found tag for topmost changelog version '%s'" % commit)
        return commit

    # Check when the changelog was last touched
    last = repo.get_commits(paths="debian/changelog", num=1)
    if last:
        gbp.log.info("Changelog last touched at '%s'" % last[0])
        return last[0]

    # Changelog not touched yet
    return None


def has_snapshot_banner(cp):
    """Whether the changelog has a snapshot banner"""
    sr = re.search(snapshot_re, cp['Changes'])
    return True if sr else False


def get_customizations(customization_file):
    if customization_file:
        execfile(customization_file,
                 user_customizations,
                 user_customizations)


def process_options(options, parser):
    if options.snapshot and options.release:
        parser.error("'--snapshot' and '--release' are incompatible options")

    if options.since and options.auto:
        parser.error("'--since' and '--auto' are incompatible options")

    dch_options = []
    if options.multimaint_merge:
        dch_options.append("--multimaint-merge")
    else:
        dch_options.append("--nomultimaint-merge")

    if options.multimaint:
        dch_options.append("--multimaint")
    else:
        dch_options.append("--nomultimaint")

    if options.force_distribution:
        dch_options.append("--force-distribution")

    get_customizations(options.customization_file)
    return dch_options


def process_editor_option(options):
    """Determine text editor and check if we need it"""
    states = ['always']

    if options.snapshot:
        states.append("snapshot")
    elif options.release:
        states.append("release")

    if options.spawn_editor == 'never' or options.spawn_editor not in states:
        return None
    else:
        return "sensible-editor"


def changelog_commit_msg(options, version):
    return options.commit_msg % dict(version=version)


def build_parser(name):
    try:
        parser = GbpOptionParserDebian(command=os.path.basename(name),
                                       usage='%prog [options] paths')
    except GbpError as err:
        gbp.log.err(err)
        return None

    range_group = GbpOptionGroup(parser, "commit range options",
                                 "which commits to add to the changelog")
    version_group = GbpOptionGroup(parser, "release & version number options",
                                   "what version number and release to use")
    commit_group = GbpOptionGroup(parser, "commit message formatting",
                                  "howto format the changelog entries")
    naming_group = GbpOptionGroup(parser, "branch and tag naming",
                                  "branch names and tag formats")
    custom_group = GbpOptionGroup(parser, "customization",
                                  "options for customization")
    parser.add_option_group(range_group)
    parser.add_option_group(version_group)
    parser.add_option_group(commit_group)
    parser.add_option_group(naming_group)
    parser.add_option_group(custom_group)

    parser.add_boolean_config_file_option(option_name="ignore-branch", dest="ignore_branch")
    naming_group.add_config_file_option(option_name="upstream-branch", dest="upstream_branch")
    naming_group.add_config_file_option(option_name="debian-branch", dest="debian_branch")
    naming_group.add_config_file_option(option_name="upstream-tag", dest="upstream_tag")
    naming_group.add_config_file_option(option_name="debian-tag", dest="debian_tag")
    naming_group.add_config_file_option(option_name="snapshot-number", dest="snapshot_number",
                                        help="expression to determine the next snapshot number, "
                                        "default is '%(snapshot-number)s'")
    parser.add_config_file_option(option_name="git-log", dest="git_log",
                                  help="options to pass to git-log, "
                                  "default is '%(git-log)s'")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    range_group.add_option("-s", "--since", dest="since", help="commit to start from (e.g. HEAD^^^, debian/0.4.3)")
    range_group.add_option("-a", "--auto", action="store_true", dest="auto", default=False,
                           help="autocomplete changelog from last snapshot or tag")
    version_group.add_option("-R", "--release", action="store_true", dest="release", default=False,
                             help="mark as release")
    version_group.add_option("-S", "--snapshot", action="store_true", dest="snapshot", default=False,
                             help="mark as snapshot build")
    version_group.add_option("-D", "--distribution", dest="distribution", help="Set distribution")
    version_group.add_option("--force-distribution", action="store_true", dest="force_distribution", default=False,
                             help="Force the provided distribution to be used, "
                             "even if it doesn't match the list of known distributions")
    version_group.add_option("-N", "--new-version", dest="new_version",
                             help="use this as base for the new version number")
    version_group.add_config_file_option("urgency", dest="urgency")
    version_group.add_option("--bpo", dest="bpo", action="store_true", default=False,
                             help="Increment the Debian release number for an upload to backports, "
                             "and add a backport upload changelog comment.")
    version_group.add_option("--nmu", dest="nmu", action="store_true", default=False,
                             help="Increment the Debian release number for a non-maintainer upload")
    version_group.add_option("--qa", dest="qa", action="store_true", default=False,
                             help="Increment the Debian release number for a Debian QA Team upload, "
                             "and add a QA upload changelog comment.")
    version_group.add_option("--team", dest="team", action="store_true", default=False,
                             help="Increment the Debian release number for a Debian Team upload, "
                             "and add a Team upload changelog comment.")
    version_group.add_option("--security", dest="security", action="store_true", default=False,
                             help="Increment the Debian release number for a security upload and "
                             "add a security upload changelog comment.")
    version_group.add_boolean_config_file_option(option_name="git-author", dest="use_git_author")
    commit_group.add_boolean_config_file_option(option_name="meta", dest="meta")
    commit_group.add_config_file_option(option_name="meta-closes", dest="meta_closes")
    commit_group.add_config_file_option(option_name="meta-closes-bugnum", dest="meta_closes_bugnum")
    commit_group.add_boolean_config_file_option(option_name="full", dest="full")
    commit_group.add_config_file_option(option_name="id-length", dest="idlen",
                                        help="include N digits of the commit id in the changelog entry, "
                                        "default is '%(id-length)s'",
                                        type="int", metavar="N")
    commit_group.add_config_file_option(option_name="ignore-regex", dest="ignore_regex",
                                        help="Ignore commit lines matching regex, "
                                        "default is '%(ignore-regex)s'")
    commit_group.add_boolean_config_file_option(option_name="multimaint", dest="multimaint")
    commit_group.add_boolean_config_file_option(option_name="multimaint-merge", dest="multimaint_merge")
    commit_group.add_config_file_option(option_name="spawn-editor", dest="spawn_editor")
    parser.add_config_file_option(option_name="commit-msg",
                                  dest="commit_msg")
    parser.add_option("-c", "--commit", action="store_true", dest="commit", default=False,
                      help="commit changelog file after generating")

    help_msg = ('Load Python code from CUSTOMIZATION_FILE.  At the moment,'
                ' the only useful thing the code can do is define a custom'
                ' format_changelog_entry() function.')
    custom_group.add_config_file_option(option_name="customizations",
                                        dest="customization_file",
                                        help=help_msg)
    return parser


def parse_args(argv):
    parser = build_parser(argv[0])
    if not parser:
        return [None] * 4

    (options, args) = parser.parse_args(argv[1:])
    gbp.log.setup(options.color, options.verbose, options.color_scheme)
    dch_options = process_options(options, parser)
    editor_cmd = process_editor_option(options)
    return options, args, dch_options, editor_cmd


def main(argv):
    ret = 0
    changelog = 'debian/changelog'
    until = 'HEAD'
    found_snapshot_banner = False
    version_change = {}
    branch = None

    options, args, dch_options, editor_cmd = parse_args(argv)

    if not options:
        return ExitCodes.parse_error

    try:
        try:
            repo = DebianGitRepository('.')
        except GitRepositoryError:
            raise GbpError("%s is not a git repository" % (os.path.abspath('.')))

        try:
            branch = repo.get_branch()
        except GitRepositoryError:
            # Not being on any branch is o.k. with --ignore-branch
            if not options.ignore_branch:
                raise

        if options.debian_branch != branch and not options.ignore_branch:
            gbp.log.err("You are not on branch '%s' but on '%s'" % (options.debian_branch, branch))
            raise GbpError("Use --ignore-branch to ignore or --debian-branch to set the branch name.")

        source = DebianSource('.')
        cp = source.changelog

        if options.since:
            since = options.since
        else:
            since = ''
            if options.auto:
                since = guess_documented_commit(cp, repo, options.debian_tag)
                if since:
                    msg = "Continuing from commit '%s'" % since
                else:
                    msg = "Starting from first commit"
                gbp.log.info(msg)
                found_snapshot_banner = has_snapshot_banner(cp)
            else:  # Fallback: continue from last tag
                since = repo.find_version(options.debian_tag, cp['Version'])
                if not since:
                    raise GbpError("Version %s not found" % cp['Version'])

        if args:
            gbp.log.info("Only looking for changes on '%s'" % " ".join(args))
        commits = repo.get_commits(since=since, until=until, paths=args,
                                   options=options.git_log.split(" "))
        commits.reverse()

        add_section = False
        # add a new changelog section if:
        if (options.new_version or options.bpo or options.nmu or options.qa or
                options.team or options.security):
            if options.bpo:
                version_change['increment'] = '--bpo'
            elif options.nmu:
                version_change['increment'] = '--nmu'
            elif options.qa:
                version_change['increment'] = '--qa'
            elif options.team:
                version_change['increment'] = '--team'
            elif options.security:
                version_change['increment'] = '--security'
            else:
                version_change['version'] = options.new_version
            # the user wants to force a new version
            add_section = True
        elif cp['Distribution'] != "UNRELEASED" and not found_snapshot_banner:
            if commits:
                # the last version was a release and we have pending commits
                add_section = True
            if options.snapshot:
                # the user want to switch to snapshot mode
                add_section = True

        if add_section and not version_change and not source.is_native():
            # Get version from upstream if none provided
            v = guess_version_from_upstream(repo, options.upstream_tag,
                                            options.upstream_branch, cp)
            if v:
                version_change['version'] = v

        i = 0
        for c in commits:
            i += 1
            parsed = parse_commit(repo, c, options,
                                  last_commit=(i == len(commits)))
            commit_msg, (commit_author, commit_email) = parsed
            if not commit_msg:
                # Some commits can be ignored
                continue

            if add_section:
                # Add a section containing just this message (we can't
                # add an empty section with dch)
                cp.add_section(distribution="UNRELEASED", msg=commit_msg,
                               version=version_change,
                               author=commit_author,
                               email=commit_email,
                               dch_options=dch_options)
                # Adding a section only needs to happen once.
                add_section = False
            else:
                cp.add_entry(commit_msg, commit_author, commit_email, dch_options)

        # Show a message if there were no commits (not even ignored
        # commits).
        if not commits:
            gbp.log.info("No changes detected from %s to %s." % (since, until))

        if add_section:
            # If we end up here, then there were no commits to include,
            # so we put a dummy message in the new section.
            cp.add_section(distribution="UNRELEASED", msg=["UNRELEASED"],
                           version=version_change,
                           dch_options=dch_options)

        fixup_section(repo, use_git_author=options.use_git_author, options=options,
                      dch_options=dch_options)

        if options.release:
            do_release(changelog, repo, cp, use_git_author=options.use_git_author,
                       dch_options=dch_options)
        elif options.snapshot:
            (snap, commit, version) = do_snapshot(changelog, repo, options.snapshot_number)
            gbp.log.info("Changelog %s (snapshot #%d) prepared up to %s" % (version, snap, commit[:7]))

        if editor_cmd:
            gbpc.Command(editor_cmd, ["debian/changelog"])()

        if options.commit:
            # Get the version from the changelog file (since dch might
            # have incremented it, there's no way we can already know
            # the version).
            version = ChangeLog(filename=changelog).version
            # Commit the changes to the changelog file
            msg = changelog_commit_msg(options, version)
            repo.commit_files([changelog], msg)
            gbp.log.info("Changelog committed for version %s" % version)
    except KeyboardInterrupt:
        ret = 1
        gbp.log.err("Interrupted. Aborting.")
    except (gbpc.CommandExecFailed,
            GbpError,
            GitRepositoryError,
            DebianSourceError,
            NoChangeLogError) as err:
        if str(err):
            gbp.log.err(err)
        ret = 1
    return ret


if __name__ == "__main__":
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
