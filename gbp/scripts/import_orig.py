# vim: set fileencoding=utf-8 :
#
# (C) 2006, 2007, 2009, 2011, 2015, 2016 Guido Guenther <agx@sigxcpu.org>
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
"""Import a new upstream version into a Git repository"""

import os
import re
import sys
import tempfile
import gbp.command_wrappers as gbpc
from gbp.deb import (DebianPkgPolicy, parse_changelog_repo)
from gbp.deb.upstreamsource import DebianUpstreamSource, unpack_component_tarball
from gbp.deb.uscan import (Uscan, UscanError)
from gbp.deb.changelog import ChangeLog, NoChangeLogError
from gbp.deb.git import (GitRepositoryError, DebianGitRepository)
from gbp.config import GbpOptionParserDebian, GbpOptionGroup, no_upstream_branch_msg
from gbp.errors import GbpError
from gbp.pkg import parse_archive_filename
from gbp.format import format_str
import gbp.log
from gbp.scripts.common import ExitCodes
from gbp.scripts.common.import_orig import (orig_needs_repack, cleanup_tmp_tree,
                                            ask_package_name, ask_package_version,
                                            repack_source, is_link_target, download_orig)
from gbp.scripts.common.hook import Hook


class RollbackError(GitRepositoryError):
    """
    An error raised if the actual rollback failed
    """
    def __init__(self, errors):
        self.msg = "Automatic rollback failed"
        super(RollbackError, self).__init__(self.msg)
        self.errors = errors

    def __str__(self):
        return "%s %s" % (self.msg, self.errors)


class ImportOrigDebianGitRepository(DebianGitRepository):
    """
    Like a DebianGitRepository but can also perform rollbacks and knows
    about some of the inner workings upstream vcs_tag, …
    """
    def __init__(self, *args, **kwargs):
        self.rollbacks = []
        self.rollback_errors = []
        DebianGitRepository.__init__(self, *args, **kwargs)

    def has_rollbacks(self):
        return len(self.rollbacks) > 0

    def vcs_tag_parent(self, vcs_tag_format, version):
        """If linking to the upstream VCS get the commit id"""
        if vcs_tag_format:
            return [self.rev_parse("%s^{}" % self.version_to_tag(vcs_tag_format, version))],
        else:
            return None

    def rrr(self, refname, action, reftype):
        """
        Remember ref for rollback

        @param refname: ref to roll back
        @param action: the rollback action (delete, reset, ...)
        @param reftype: the reference type (tag, branch, ...)
        """
        sha = None

        if action == 'reset':
            try:
                sha = self.rev_parse(refname)
            except GitRepositoryError as err:
                gbp.log.warn("Failed to rev-parse %s: %s" % (refname, err))
        elif action == 'delete':
            pass
        elif action == 'abortmerge':
            pass
        else:
            raise GbpError("Unknown action %s for %s %s" % (action, reftype, refname))
        self.rollbacks.append((refname, reftype, action, sha))

    def rrr_branch(self, branchname, action='reset-or-delete'):
        if action == 'reset-or-delete':
            if self.has_branch(branchname):
                return self.rrr(branchname, 'reset', 'branch')
            else:
                return self.rrr(branchname, 'delete', 'branch')
        else:
            return self.rrr(branchname, action, 'branch')

    def rrr_tag(self, tagname, action='delete'):
        return self.rrr(tagname, action, 'tag')

    def rrr_merge(self, commit, action='abortmerge'):
        return self.rrr(commit, action, 'commit')

    def rollback(self):
        """
        Perform a complete rollback

        Try to roll back as much as possible and remember what failed.
        """
        for (name, reftype, action, sha) in self.rollbacks:
            try:
                if action == 'delete':
                    gbp.log.info('Rolling back %s %s by deleting it' % (reftype, name))
                    if reftype == 'tag':
                        self.delete_tag(name)
                    elif reftype == 'branch':
                        self.delete_branch(name)
                    else:
                        raise GitRepositoryError("Don't know how to delete %s %s" % (reftype, name))
                elif action == 'reset' and reftype == 'branch':
                    gbp.log.info('Rolling back branch %s by resetting it to %s' % (name, sha))
                    self.update_ref("refs/heads/%s" % name, sha, msg="gbp import-orig: failure rollback of %s" % name)
                elif action == 'abortmerge':
                    gbp.log.info('Rolling back failed merge of %s' % name)
                    self.abort_merge()
                else:
                    raise GitRepositoryError("Don't know how to %s %s %s" % (action, reftype, name))
            except GitRepositoryError as e:
                self.rollback_errors.append((name, reftype, action, sha, e))
        if self.rollback_errors:
            raise RollbackError(self.rollback_errors)

    # Wrapped methods for rollbacks
    def create_tag(self, *args, **kwargs):
        name = kwargs['name']
        ret = super(ImportOrigDebianGitRepository, self).create_tag(*args, **kwargs)
        self.rrr_tag(name)
        return ret

    def commit_dir(self, *args, **kwargs):
        import_branch = kwargs['branch']
        self.rrr_branch(import_branch)
        return super(ImportOrigDebianGitRepository, self).commit_dir(*args, **kwargs)

    def create_branch(self, *args, **kwargs):
        branch = kwargs['branch']
        ret = super(ImportOrigDebianGitRepository, self).create_branch(*args, **kwargs)
        self.rrr_branch(branch, 'delete')
        return ret

    def merge(self, *args, **kwargs):
        commit = args[0] if args else kwargs['commit']
        try:
            return super(ImportOrigDebianGitRepository, self).merge(*args, **kwargs)
        except GitRepositoryError:
            # Only cleanup in the error case to undo working copy
            # changes. Resetting the refs handles the other cases.
            self.rrr_merge(commit)
            raise


def prepare_pristine_tar(archive, pkg, version):
    """
    Prepare the upstream source for pristine tar import.

    This checks if the upstream source is actually a tarball
    and creates a symlink from I{archive}
    to I{<pkg>_<version>.orig.tar.<ext>} so pristine-tar will
    see the correct basename.

    @param archive: the upstream source's name
    @type archive: C{str}
    @param pkg: the source package's name
    @type pkg: C{str}
    @param version: the upstream version number
    @type version: C{str}
    @rtype: C{str}
    """
    linked = False
    if os.path.isdir(archive):
        return None

    ext = os.path.splitext(archive)[1]
    if ext in ['.tgz', '.tbz2', '.tlz', '.txz']:
        ext = ".%s" % ext[2:]

    link = "../%s_%s.orig.tar%s" % (pkg, version, ext)

    if os.path.basename(archive) != os.path.basename(link):
        try:
            if not is_link_target(archive, link):
                os.symlink(os.path.abspath(archive), link)
                linked = True
        except OSError as err:
                raise GbpError("Cannot symlink '%s' to '%s': %s" % (archive, link, err[1]))
        return (link, linked)
    else:
        return (archive, linked)


def upstream_import_commit_msg(options, version):
    return options.import_msg % dict(version=version)


def detect_name_and_version(repo, source, options):
    # Guess defaults for the package name and version from the
    # original tarball.
    guessed_package, guessed_version = source.guess_version()

    # Try to find the source package name
    try:
        cp = ChangeLog(filename='debian/changelog')
        sourcepackage = cp['Source']
    except NoChangeLogError:
        try:
            # Check the changelog file from the repository, in case
            # we're not on the debian-branch (but upstream, for
            # example).
            cp = parse_changelog_repo(repo, options.debian_branch, 'debian/changelog')
            sourcepackage = cp['Source']
        except NoChangeLogError:
            if options.interactive:
                sourcepackage = ask_package_name(guessed_package,
                                                 DebianPkgPolicy.is_valid_packagename,
                                                 DebianPkgPolicy.packagename_msg)
            else:
                if guessed_package:
                    sourcepackage = guessed_package
                else:
                    raise GbpError("Couldn't determine upstream package name. Use --interactive.")

    # Try to find the version.
    if options.version:
        version = options.version
    else:
        if options.interactive:
            version = ask_package_version(guessed_version,
                                          DebianPkgPolicy.is_valid_upstreamversion,
                                          DebianPkgPolicy.upstreamversion_msg)
        else:
            if guessed_version:
                version = guessed_version
            else:
                raise GbpError("Couldn't determine upstream version. Use '-u<version>' or --interactive.")

    return (sourcepackage, version)


def find_source(use_uscan, args):
    """Find the main tarball to import - either via uscan or via command line argument
    @return: upstream source filename or None if nothing to import
    @rtype: string
    @raise GbpError: raised on all detected errors

    >>> find_source(False, ['too', 'many'])
    Traceback (most recent call last):
    ...
    GbpError: More than one archive specified. Try --help.
    >>> find_source(False, [])
    Traceback (most recent call last):
    ...
    GbpError: No archive to import specified. Try --help.
    >>> find_source(True, ['tarball'])
    Traceback (most recent call last):
    ...
    GbpError: you can't pass both --uscan and a filename.
    >>> find_source(False, ['tarball']).path
    'tarball'
    """
    if use_uscan:
        if args:
            raise GbpError("you can't pass both --uscan and a filename.")

        uscan = Uscan()
        gbp.log.info("Launching uscan...")
        try:
            uscan.scan()
        except UscanError as e:
            raise GbpError("%s" % e)

        if not uscan.uptodate:
            if uscan.tarball:
                gbp.log.info("using %s" % uscan.tarball)
                args.append(uscan.tarball)
            else:
                raise GbpError("uscan didn't download anything, and no source was found in ../")
        else:
            gbp.log.info("package is up to date, nothing to do.")
            return None
    if len(args) > 1:  # source specified
        raise GbpError("More than one archive specified. Try --help.")
    elif len(args) == 0:
        raise GbpError("No archive to import specified. Try --help.")
    else:
        return DebianUpstreamSource(args[0])


def debian_branch_merge(repo, tag, version, options):
    try:
        func = globals()["debian_branch_merge_by_%s" % options.merge_mode]
    except KeyError:
        raise GbpError("%s is not a valid merge mode" % options.merge_mode)
    func(repo, tag, version, options)
    if options.postimport:
        epoch = ''
        if os.access('debian/changelog', os.R_OK):
            # No need to check the changelog file from the
            # repository, since we're certain that we're on
            # the debian-branch
            cp = ChangeLog(filename='debian/changelog')
            if cp.has_epoch():
                epoch = '%s:' % cp.epoch
        debian_version = "%s%s-1" % (epoch, version)
        info = {'version': debian_version}
        env = {'GBP_BRANCH': options.debian_branch,
               'GBP_TAG': tag,
               'GBP_UPSTREAM_VERSION': version,
               'GBP_DEBIAN_VERSION': debian_version,
               }
        Hook('Postimport',
             format_str(options.postimport, info),
             extra_env=env)()


def debian_branch_merge_by_replace(repo, tag, version, options):
    gbp.log.info("Replacing upstream source on '%s'" % options.debian_branch)

    tree = [x for x in repo.list_tree("%s^{tree}" % tag)
            if x[-1] != 'debian']
    msg = "Updated version %s from '%s'" % (version, tag)

    # Get the current debian/ tree on the debian branch
    try:
        deb_sha = [x for x in repo.list_tree("%s^{tree}" % options.debian_branch)
                   if x[-1] == 'debian' and x[1] == 'tree'][0][2]
        tree.append(['040000', 'tree', deb_sha, 'debian'])
        msg += "\n\nwith Debian dir %s" % deb_sha
    except IndexError:
        pass  # no debian/ dir is fine

    sha = repo.make_tree(tree)
    commit = repo.commit_tree(sha, msg, ["%s^{commit}" % options.debian_branch,
                                         "%s^{commit}" % tag])
    repo.update_ref("refs/heads/%s" % options.debian_branch, commit,
                    msg="gbp: Updating %s after import of %s" % (options.debian_branch,
                                                                 tag))
    repo.force_head(commit, hard=True)


def get_component_tarballs(name, version, tarball, components):
    """
    Figure out the paths to the component tarballs based on the main
    tarball.
    """
    tarballs = []
    for component in components:
        (_, _, comp_type) = parse_archive_filename(tarball)
        cname = DebianPkgPolicy.build_tarball_name(name,
                                                   version,
                                                   comp_type,
                                                   os.path.dirname(tarball),
                                                   component)
        tarballs.append((component, cname))
        if not os.path.exists(cname):
            raise GbpError("Can not find component tarball %s" % cname)
    return tarballs


def debian_branch_merge_by_merge(repo, tag, version, options):
    gbp.log.info("Merging to '%s'" % options.debian_branch)
    branch = repo.get_branch()
    repo.set_branch(options.debian_branch)
    try:
        repo.merge(tag)
    except GitRepositoryError:
        raise GbpError("Automatic merge failed.")
    repo.set_branch(branch)


def set_bare_repo_options(options):
    """Modify options for import into a bare repository"""
    if options.pristine_tar or options.merge:
        gbp.log.info("Bare repository: setting %s%s options"
                     % (["", " '--no-pristine-tar'"][options.pristine_tar],
                        ["", " '--no-merge'"][options.merge]))
        options.pristine_tar = False
        options.merge = False


def build_parser(name):
    try:
        parser = GbpOptionParserDebian(command=os.path.basename(name), prefix='',
                                       usage='%prog [options] /path/to/upstream-version.tar.gz | --uscan')
    except GbpError as err:
        gbp.log.err(err)
        return None

    import_group = GbpOptionGroup(parser, "import options",
                                  "pristine-tar and filtering")
    tag_group = GbpOptionGroup(parser, "tag options",
                               "options related to git tag creation")
    branch_group = GbpOptionGroup(parser, "version and branch naming options",
                                  "version number and branch layout options")
    cmd_group = GbpOptionGroup(parser, "external command options",
                               "how and when to invoke external commands and hooks")
    for group in [import_group, branch_group, tag_group, cmd_group]:
        parser.add_option_group(group)

    branch_group.add_option("-u", "--upstream-version", dest="version",
                            help="Upstream Version")
    branch_group.add_config_file_option(option_name="debian-branch",
                                        dest="debian_branch")
    branch_group.add_config_file_option(option_name="upstream-branch",
                                        dest="upstream_branch")
    branch_group.add_config_file_option(option_name="upstream-vcs-tag", dest="vcs_tag",
                                        help="Upstream VCS tag add to the merge commit")
    branch_group.add_boolean_config_file_option(option_name="merge", dest="merge")
    branch_group.add_config_file_option(option_name="merge-mode", dest="merge_mode")

    tag_group.add_boolean_config_file_option(option_name="sign-tags",
                                             dest="sign_tags")
    tag_group.add_config_file_option(option_name="keyid",
                                     dest="keyid")
    tag_group.add_config_file_option(option_name="upstream-tag",
                                     dest="upstream_tag")
    import_group.add_config_file_option(option_name="filter",
                                        dest="filters", action="append")
    import_group.add_boolean_config_file_option(option_name="pristine-tar",
                                                dest="pristine_tar")
    import_group.add_boolean_config_file_option(option_name="filter-pristine-tar",
                                                dest="filter_pristine_tar")
    import_group.add_config_file_option(option_name="import-msg",
                                        dest="import_msg")
    import_group.add_boolean_config_file_option(option_name="symlink-orig",
                                                dest="symlink_orig")
    import_group.add_config_file_option("component", action="append", metavar='COMPONENT',
                                        dest="components")
    cmd_group.add_config_file_option(option_name="postimport", dest="postimport")

    parser.add_boolean_config_file_option(option_name="interactive",
                                          dest='interactive')
    parser.add_boolean_config_file_option(option_name="rollback",
                                          dest="rollback")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")

    # Accepted for compatibility
    parser.add_option("--no-dch", dest='no_dch', action="store_true",
                      default=False, help="deprecated - don't use.")
    parser.add_option("--uscan", dest='uscan', action="store_true",
                      default=False, help="use uscan(1) to download the new tarball.")
    parser.add_option("--download", dest='download', action="store_true",
                      default=False, help="Ignored. Accepted for compatibility.")
    return parser


def parse_args(argv):
    """Parse the command line arguments
    @return: options and arguments
    """

    parser = build_parser(argv[0])
    if not parser:
        return None, None

    (options, args) = parser.parse_args(argv[1:])
    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    if options.no_dch:
        gbp.log.warn("'--no-dch' passed. This is now the default, please remove this option.")

    if options.download:
        gbp.log.warn("Passing --download explicitly is deprecated.")

    options.download = is_download(args)
    return options, args


def is_download(args):
    """
    >>> is_download(["http://foo.example.com"])
    True
    >>> is_download([])
    False
    >>> is_download(["foo-1.1.orig.tar.gz"])
    False
    """
    if args and re.match("https?://", args[0]):
        return True
    return False


def main(argv):
    ret = 0
    tmpdir = ''
    pristine_orig = None
    linked = False
    repo = None

    (options, args) = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    try:
        try:
            repo = ImportOrigDebianGitRepository('.')
        except GitRepositoryError:
            raise GbpError("%s is not a git repository" % (os.path.abspath('.')))

        is_empty = repo.is_empty()

        if not repo.has_branch(options.upstream_branch) and not is_empty:
            raise GbpError(no_upstream_branch_msg % options.upstream_branch)

        (clean, out) = repo.is_clean()
        if not clean and not is_empty:
            gbp.log.err("Repository has uncommitted changes, commit these first: ")
            raise GbpError(out)

        # Download the main tarball
        if options.download:
            source = download_orig(args[0])
        else:
            source = find_source(options.uscan, args)
        if not source:
            return ret

        # The main tarball
        (sourcepackage, version) = detect_name_and_version(repo, source, options)
        # Additionl tarballs we expect to exist
        component_tarballs = get_component_tarballs(sourcepackage,
                                                    version,
                                                    source.path,
                                                    options.components)

        tag = repo.version_to_tag(options.upstream_tag, version)
        if repo.has_tag(tag):
            raise GbpError("Upstream tag '%s' already exists" % tag)

        if repo.bare:
            set_bare_repo_options(options)

        if not source.is_dir():
            tmpdir = tempfile.mkdtemp(dir='../')
            source.unpack(tmpdir, options.filters)
            gbp.log.debug("Unpacked '%s' to '%s'" % (source.path, source.unpacked))
            for (component, tarball) in component_tarballs:
                unpack_component_tarball(source.unpacked, component, tarball, options.filters)

        if orig_needs_repack(source, options):
            gbp.log.debug("Filter pristine-tar: repacking '%s' from '%s'" % (source.path, source.unpacked))
            (source, tmpdir) = repack_source(source, sourcepackage, version, tmpdir, options.filters)

        (pristine_orig, linked) = prepare_pristine_tar(source.path,
                                                       sourcepackage,
                                                       version)

        # Don't mess up our repo with git metadata from an upstream tarball
        try:
            if os.path.isdir(os.path.join(source.unpacked, '.git/')):
                raise GbpError("The orig tarball contains .git metadata - giving up.")
        except OSError:
            pass

        try:
            import_branch = options.upstream_branch
            filter_msg = ["", " (filtering out %s)"
                              % options.filters][len(options.filters) > 0]
            gbp.log.info("Importing '%s' to branch '%s'%s..." % (source.path,
                                                                 import_branch,
                                                                 filter_msg))
            gbp.log.info("Source package is %s" % sourcepackage)
            gbp.log.info("Upstream version is %s" % version)

            msg = upstream_import_commit_msg(options, version)

            commit = repo.commit_dir(source.unpacked,
                                     msg=msg,
                                     branch=import_branch,
                                     other_parents=repo.vcs_tag_parent(options.vcs_tag, version),
                                     create_missing_branch=is_empty,
                                     )

            if options.pristine_tar:
                if pristine_orig:
                    repo.rrr_branch('pristine-tar')
                    repo.create_pristinetar_commits(import_branch,
                                                    pristine_orig,
                                                    component_tarballs)
                else:
                    gbp.log.warn("'%s' not an archive, skipping pristine-tar" % source.path)

            repo.create_tag(name=tag,
                            msg="Upstream version %s" % version,
                            commit=commit,
                            sign=options.sign_tags,
                            keyid=options.keyid)

            if is_empty:
                repo.create_branch(branch=options.debian_branch, rev=commit)
                repo.force_head(options.debian_branch, hard=True)
            elif options.merge:
                repo.rrr_branch(options.debian_branch)
                debian_branch_merge(repo, tag, version, options)

            # Update working copy and index if we've possibly updated the
            # checked out branch
            current_branch = repo.get_branch()
            if current_branch in [options.upstream_branch,
                                  repo.pristine_tar_branch]:
                repo.force_head(current_branch, hard=True)
        except (gbpc.CommandExecFailed, GitRepositoryError) as err:
            msg = str(err) or 'Unknown error, please report a bug'
            raise GbpError("Import of %s failed: %s" % (source.path, msg))
    except GbpError as err:
        if str(err):
            gbp.log.err(err)
        ret = 1
        if repo and repo.has_rollbacks() and options.rollback:
            gbp.log.err("Error detected, Will roll back changes.")
            try:
                repo.rollback()
                # Make sure the very last line as an error message
                gbp.log.err("Rolled back changes after import error.")
            except Exception as e:
                gbp.log.err("%s" % e)
                gbp.log.err("Clean up manually and please report a bug: %s" %
                            repo.rollback_errors)

    if pristine_orig and linked and not options.symlink_orig:
        os.unlink(pristine_orig)

    if tmpdir:
        cleanup_tmp_tree(tmpdir)

    if not ret:
        gbp.log.info("Successfully imported version %s of %s" % (version, source.path))
    return ret


if __name__ == "__main__":
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
