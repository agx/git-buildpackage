# vim: set fileencoding=utf-8 :
#
# (C) 2006, 2007, 2009, 2011 Guido Guenther <agx@sigxcpu.org>
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
#
"""Import a new upstream version into a git repository"""

import ConfigParser
import glob
import os
import sys
import re
import subprocess
import tempfile
import gbp.command_wrappers as gbpc
from gbp.deb import (UpstreamSource,
                     do_uscan,
                     parse_changelog_repo, is_valid_packagename,
                     packagename_msg, is_valid_upstreamversion,
                     upstreamversion_msg)
from gbp.deb.changelog import ChangeLog, NoChangeLogError
from gbp.deb.git import (GitRepositoryError, DebianGitRepository)
from gbp.config import GbpOptionParser, GbpOptionGroup, no_upstream_branch_msg
from gbp.errors import (GbpError, GbpNothingImported)
import gbp.log

# Try to import readline, since that will cause raw_input to get fancy
# line editing and history capabilities. However, if readline is not
# available, raw_input will still work.
try:
    import readline
except ImportError:
    pass


class OrigUpstreamSource(UpstreamSource):
    """Upstream source that will be imported"""

    def needs_repack(self, options):
        """
        Determine if the upstream sources needs to be repacked

        We repack if
         1. we want to filter out files and use pristine tar since we want
            to make a filtered tarball available to pristine-tar
         2. when we don't have a suitable upstream tarball (e.g. zip archive or unpacked dir)
            and want to use filters
         3. when we don't have a suitable upstream tarball (e.g. zip archive or unpacked dir)
            and want to use pristine-tar
        """
        if ((options.pristine_tar and options.filter_pristine_tar and len(options.filters) > 0)):
            return True
        elif not self.is_orig:
            if len(options.filters):
                return True
            elif options.pristine_tar:
                return True
        return False


def cleanup_tmp_tree(tree):
    """remove a tree of temporary files"""
    try:
        gbpc.RemoveTree(tree)()
    except gbpc.CommandExecFailed:
        gbp.log.err("Removal of tmptree %s failed." % tree)


def is_link_target(target, link):
    """does symlink link already point to target?"""
    if os.path.exists(link):
            if os.path.samefile(target, link):
                return True
    return False


def symlink_orig(archive, pkg, version):
    """
    create a symlink <pkg>_<version>.orig.tar.<ext> so pristine-tar will see the
    correct basename
    @return: archive path to be used by pristine tar
    """
    if os.path.isdir(archive):
        return None
    ext = os.path.splitext(archive)[1]
    link = "../%s_%s.orig.tar%s" % (pkg, version, ext)
    if os.path.basename(archive) != os.path.basename(link):
        try:
            if not is_link_target(archive, link):
                os.symlink(os.path.abspath(archive), link)
        except OSError, err:
                raise GbpError, "Cannot symlink '%s' to '%s': %s" % (archive, link, err[1])
        return link
    else:
        return archive


def upstream_import_commit_msg(options, version):
    return options.import_msg % dict(version=version)


def detect_name_and_version(repo, source, options):
    # Guess defaults for the package name and version from the
    # original tarball.
    (guessed_package, guessed_version) = source.guess_version() or ('', '')

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
                sourcepackage = ask_package_name(guessed_package)
            else:
                if guessed_package:
                    sourcepackage = guessed_package
                else:
                    raise GbpError, "Couldn't determine upstream package name. Use --interactive."

    # Try to find the version.
    if options.version:
        version = options.version
    else:
        if options.interactive:
            version = ask_package_version(guessed_version)
        else:
            if guessed_version:
                version = guessed_version
            else:
                raise GbpError, "Couldn't determine upstream version. Use '-u<version>' or --interactive."

    return (sourcepackage, version)


def ask_package_name(default):
    """
    Ask the user for the source package name.
    @param default: The default package name to suggest to the user.
    """
    while True:
        sourcepackage = raw_input("What will be the source package name? [%s] " % default)
        if not sourcepackage: # No input, use the default.
            sourcepackage = default
        # Valid package name, return it.
        if is_valid_packagename(sourcepackage):
            return sourcepackage

        # Not a valid package name. Print an extra
        # newline before the error to make the output a
        # bit clearer.
        gbp.log.warn("\nNot a valid package name: '%s'.\n%s" % (sourcepackage, packagename_msg))


def ask_package_version(default):
    """
    Ask the user for the upstream package version.
    @param default: The default package version to suggest to the user.
    """
    while True:
        version = raw_input("What is the upstream version? [%s] " % default)
        if not version: # No input, use the default.
            version = default
        # Valid version, return it.
        if is_valid_upstreamversion(version):
            return version

        # Not a valid upstream version. Print an extra
        # newline before the error to make the output a
        # bit clearer.
        gbp.log.warn("\nNot a valid upstream version: '%s'.\n%s" % (version, upstreamversion_msg))


def find_source(options, args):
    """Find the tarball to import - either via uscan or via command line argument
    @return: upstream source filename or None if nothing to import
    @rtype: string
    @raise GbpError: raised on all detected errors
    """
    if options.uscan: # uscan mode
        if args:
            raise GbpError, "you can't pass both --uscan and a filename."

        gbp.log.info("Launching uscan...")
        try:
            status, source = do_uscan()
        except KeyError:
            raise GbpError, "error running uscan - debug by running uscan --verbose"

        if status:
            if source:
                gbp.log.info("using %s" % source)
                args.append(source)
            else:
                raise GbpError, "uscan didn't download anything, and no source was found in ../"
        else:
            gbp.log.info("package is up to date, nothing to do.")
            return None
    if len(args) > 1: # source specified
        raise GbpError, "More than one archive specified. Try --help."
    elif len(args) == 0:
        raise GbpError, "No archive to import specified. Try --help."
    else:
        archive = OrigUpstreamSource(args[0])
        return archive


def repacked_tarball_name(source, name, version):
    if source.is_orig:
        # Repacked orig tarballs get need a different name since there's already
        # one with that name
        name = os.path.join(
                    os.path.dirname(source.path),
                    os.path.basename(source.path).replace(".tar", ".gbp.tar"))
    else:
        # Repacked sources or other archives get canonical name
        name = os.path.join(
                    os.path.dirname(source.path),
                    "%s_%s.orig.tar.bz2" % (name, version))
    return name


def repack_source(source, name, version, tmpdir, filters):
    """Repack the source tree"""
    name = repacked_tarball_name(source, name, version)
    repacked = source.pack(name, filters)
    if source.is_orig: # the tarball was filtered on unpack
        repacked.unpacked = source.unpacked
    else: # otherwise unpack the generated tarball get a filtered tree
        if tmpdir:
            cleanup_tmp_tree(tmpdir)
        tmpdir = tempfile.mkdtemp(dir='../')
        repacked.unpack(tmpdir, filters)
    return (repacked, tmpdir)


def set_bare_repo_options(options):
    """Modify options for import into a bare repository"""
    if options.pristine_tar or options.merge:
        gbp.log.info("Bare repository: setting %s%s options"
                      % (["", " '--no-pristine-tar'"][options.pristine_tar],
                         ["", " '--no-merge'"][options.merge]))
        options.pristine_tar = False
        options.merge = False


def parse_args(argv):
    try:
        parser = GbpOptionParser(command=os.path.basename(argv[0]), prefix='',
                                 usage='%prog [options] /path/to/upstream-version.tar.gz | --uscan')
    except ConfigParser.ParsingError, err:
        gbp.log.err(err)
        return None, None

    import_group = GbpOptionGroup(parser, "import options",
                      "pristine-tar and filtering")
    tag_group = GbpOptionGroup(parser, "tag options",
                      "options related to git tag creation")
    branch_group = GbpOptionGroup(parser, "version and branch naming options",
                      "version number and branch layout options")
    cmd_group = GbpOptionGroup(parser, "external command options", "how and when to invoke external commands and hooks")

    for group in [import_group, branch_group, tag_group, cmd_group ]:
        parser.add_option_group(group)

    branch_group.add_option("-u", "--upstream-version", dest="version",
                      help="Upstream Version")
    branch_group.add_config_file_option(option_name="debian-branch",
                      dest="debian_branch")
    branch_group.add_config_file_option(option_name="upstream-branch",
                      dest="upstream_branch")
    branch_group.add_boolean_config_file_option(option_name="merge", dest="merge")

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
    cmd_group.add_config_file_option(option_name="postimport", dest="postimport")

    parser.add_boolean_config_file_option(option_name="interactive",
                                          dest='interactive')
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')

    # Accepted for compatibility
    parser.add_option("--no-dch", dest='no_dch', action="store_true",
                      default=False, help="deprecated - don't use.")
    parser.add_option("--uscan", dest='uscan', action="store_true",
                      default=False, help="use uscan(1) to download the new tarball.")

    (options, args) = parser.parse_args(argv[1:])
    gbp.log.setup(options.color, options.verbose)

    if options.no_dch:
        gbp.log.warn("'--no-dch' passed. This is now the default, please remove this option.")

    return options, args


def main(argv):
    ret = 0
    tmpdir = ''
    pristine_orig = None

    (options, args) = parse_args(argv)
    try:
        source = find_source(options, args)
        if not source:
            return ret

        try:
            repo = DebianGitRepository('.')
        except GitRepositoryError:
            raise GbpError, "%s is not a git repository" % (os.path.abspath('.'))

        # an empty repo has now branches:
        initial_branch = repo.get_branch()
        is_empty = False if initial_branch else True

        if not repo.has_branch(options.upstream_branch) and not is_empty:
            gbp.log.err(no_upstream_branch_msg % options.upstream_branch)
            raise GbpError

        (sourcepackage, version) = detect_name_and_version(repo, source, options)

        (clean, out) = repo.is_clean()
        if not clean and not is_empty:
            gbp.log.err("Repository has uncommitted changes, commit these first: ")
            raise GbpError, out

        if repo.bare:
            set_bare_repo_options(options)

        if not source.is_dir:
            tmpdir = tempfile.mkdtemp(dir='../')
            source.unpack(tmpdir, options.filters)
            gbp.log.debug("Unpacked '%s' to '%s'" % (source.path, source.unpacked))

        if source.needs_repack(options):
            gbp.log.debug("Filter pristine-tar: repacking '%s' from '%s'" % (source.path, source.unpacked))
            (source, tmpdir)  = repack_source(source, sourcepackage, version, tmpdir, options.filters)

        pristine_orig = symlink_orig(source.path, sourcepackage, version)

        # Don't mess up our repo with git metadata from an upstream tarball
        try:
            if os.path.isdir(os.path.join(source.unpacked, '.git/')):
                raise GbpError, "The orig tarball contains .git metadata - giving up."
        except OSError:
            pass

        try:
            upstream_branch = [ options.upstream_branch, 'master' ][is_empty]
            filter_msg = ["", " (filtering out %s)"
                              % options.filters][len(options.filters) > 0]
            gbp.log.info("Importing '%s' to branch '%s'%s..." % (source.path,
                                                                 upstream_branch,
                                                                 filter_msg))
            gbp.log.info("Source package is %s" % sourcepackage)
            gbp.log.info("Upstream version is %s" % version)

            import_branch = [ options.upstream_branch, None ][is_empty]
            msg = upstream_import_commit_msg(options, version)
            commit = repo.commit_dir(source.unpacked, msg=msg, branch=import_branch)
            if not commit:
                raise GbpError, "Import of upstream version %s failed." % version

            if options.pristine_tar:
                if pristine_orig:
                    repo.pristine_tar.commit(pristine_orig, upstream_branch)
                else:
                    gbp.log.warn("'%s' not an archive, skipping pristine-tar" % source.path)

            tag = repo.version_to_tag(options.upstream_tag, version)
            repo.create_tag(name=tag,
                            msg="Upstream version %s" % version,
                            commit=commit,
                            sign=options.sign_tags,
                            keyid=options.keyid)
            if is_empty:
                repo.create_branch(options.upstream_branch, rev=commit)
                repo.force_head(options.upstream_branch, hard=True)
            elif options.merge:
                gbp.log.info("Merging to '%s'" % options.debian_branch)
                repo.set_branch(options.debian_branch)
                try:
                    repo.merge(tag)
                except gbpc.CommandExecFailed:
                    raise GbpError, """Merge failed, please resolve."""
                if options.postimport:
                    epoch = ''
                    if os.access('debian/changelog', os.R_OK):
                        # No need to check the changelog file from the
                        # repository, since we're certain that we're on
                        # the debian-branch
                        cp = ChangeLog(filename='debian/changelog')
                        if cp.has_epoch():
                            epoch = '%s:' % cp.epoch
                    info = { 'version': "%s%s-1" % (epoch, version) }
                    env = { 'GBP_BRANCH': options.debian_branch }
                    gbpc.Command(options.postimport % info, extra_env=env, shell=True)()
        except gbpc.CommandExecFailed:
            raise GbpError, "Import of %s failed" % source.path
    except GbpNothingImported, err:
        gbp.log.err(err)
        repo.set_branch(initial_branch)
        ret = 1
    except GbpError, err:
        if len(err.__str__()):
            gbp.log.err(err)
        ret = 1

    if tmpdir:
        cleanup_tmp_tree(tmpdir)

    if not ret:
        gbp.log.info("Successfully imported version %s of %s" % (version, source.path))
    return ret

if __name__ == "__main__":
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
