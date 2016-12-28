# vim: set fileencoding=utf-8 :
#
# (C) 2006, 2007, 2011, 2012, 2015, 2016 Guido Guenther <agx@sigxcpu.org>
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
"""Import a Debian source package into a Git repository"""

import sys
import re
import os
import shutil
import tempfile
import glob
import pipes
import time
import gbp.command_wrappers as gbpc
from gbp.deb.dscfile import DscFile
from gbp.deb.upstreamsource import DebianUpstreamSource, unpack_component_tarball
from gbp.deb.git import (DebianGitRepository, GitRepositoryError)
from gbp.deb.changelog import ChangeLog
from gbp.git import rfc822_date_to_git
from gbp.git.modifier import GitModifier
from gbp.config import (GbpOptionParserDebian, GbpOptionGroup,
                        no_upstream_branch_msg)
from gbp.errors import GbpError
from gbp.scripts.common import ExitCodes
from gbp.scripts.common import repo_setup
import gbp.log


class SkipImport(Exception):
    pass


def download_source(pkg, dirs, unauth):
    opts = ['--download-only']
    if unauth:
        opts.append('--allow-unauthenticated')

    if re.match(r'[a-z]{1,5}://', pkg):
        cmd = 'dget'
        opts += ['-q', pkg]
    else:
        cmd = 'apt-get'
        opts += ['-qq', 'source', pkg]

    dirs['download'] = os.path.abspath(tempfile.mkdtemp())
    gbp.log.info("Downloading '%s' using '%s'..." % (pkg, cmd))

    gbpc.RunAtCommand(cmd, opts, shell=False)(dir=dirs['download'])
    try:
        dsc = glob.glob(os.path.join(dirs['download'], '*.dsc'))[0]
    except IndexError:
        raise GbpError("Did not find a dsc file at %s/" % dirs['download'])
    return dsc


def apply_patch(diff):
    "Apply patch to a source tree"
    patch_opts = ['-N', '-p1', '-F0', '-u', '-t',
                  '-Vnever', '-g0', '-z.gbp.orig',
                  '--quiet']

    pipe = pipes.Template()
    pipe.prepend('gunzip -c %s' % diff, '.-')
    pipe.append('patch %s' % ' '.join(patch_opts), '-.')

    try:
        ret = pipe.copy('', '')
        if ret:
            gbp.log.err("Error import %s: %d" % (diff, ret))
            return False
    except OSError as err:
        gbp.log.err("Error importing %s: %s" % (diff, err[0]))
        return False
    return True


def apply_deb_tgz(deb_tgz):
    """Apply .debian.tar.gz (V3 source format)"""
    # Remove any existing data in debian/ as dpkg-source -x does
    if os.path.isdir('debian'):
        shutil.rmtree('debian')
    gbpc.UnpackTarArchive(deb_tgz, ".")()
    return True


def get_author_from_changelog(dir):
    """
    Get author from debian/changelog
    """
    dch = ChangeLog(filename=os.path.join(dir, 'debian/changelog'))
    date = rfc822_date_to_git(dch.date)
    if not (dch.author or dch.email):
        gbp.log.warn("Failed to parse maintainer")

    return GitModifier(dch.author, dch.email, date)


def get_committer_from_author(author, options):
    """
    Based on the options fill in the committer
    """
    committer = GitModifier()
    if options.author_committer:
        committer.name = author.name
        committer.email = author.email
    if options.author_committer_date:
        committer.date = author.date
    return committer


def check_parents(repo, branch, tag):
    """
    Check if the upstream tag is already merged, if not, return
    the additional parent to merge
    """
    parents = None
    rev = None

    try:
        rev = repo.rev_parse("%s^{commit}" % tag)
    except GitRepositoryError:
        pass

    if rev and not repo.branch_contains(branch, rev):
        gbp.log.debug("Tag '%s' not yet merged into '%s'"
                      % (tag, branch))
        parents = [rev]

    return parents


def apply_debian_patch(repo, unpack_dir, src, options, tag):
    """apply the debian patch and tag appropriately"""
    try:
        os.chdir(unpack_dir)

        if src.diff and not apply_patch(src.diff):
            raise GbpError

        if src.deb_tgz and not apply_deb_tgz(src.deb_tgz):
            raise GbpError

        if os.path.exists('debian/rules'):
            os.chmod('debian/rules', 0o755)
        os.chdir(repo.path)

        parents = check_parents(repo,
                                options.debian_branch,
                                tag)

        author = get_author_from_changelog(unpack_dir)
        committer = get_committer_from_author(author, options)
        commit = repo.commit_dir(unpack_dir,
                                 "Import Debian patch %s" % src.version,
                                 branch=options.debian_branch,
                                 other_parents=parents,
                                 author=author,
                                 committer=committer)
        if not options.skip_debian_tag:
            repo.create_tag(repo.version_to_tag(options.debian_tag, src.version),
                            msg="Debian release %s" % src.version,
                            commit=commit,
                            sign=options.sign_tags,
                            keyid=options.keyid)
    except (gbpc.CommandExecFailed, GitRepositoryError) as err:
        msg = str(err) or 'Unknown error, please report a bug'
        gbp.log.err("Failed to import Debian package: %s" % msg)
        raise GbpError
    finally:
        os.chdir(repo.path)


def print_dsc(dsc):
    if dsc.native:
        gbp.log.debug("Debian Native Package")
        gbp.log.debug("Version: %s" % dsc.upstream_version)
        gbp.log.debug("Debian tarball: %s" % dsc.tgz)
    else:
        gbp.log.debug("Upstream version: %s" % dsc.upstream_version)
        gbp.log.debug("Debian version: %s" % dsc.debian_version)
        gbp.log.debug("Upstream tarball: %s" % dsc.tgz)
        if dsc.additional_tarballs:
            gbp.log.debug("Additional tarballs: %s" % ", ".join(dsc.additional_tarballs.values()))
        if dsc.diff:
            gbp.log.debug("Debian patch: %s" % dsc.diff)
        if dsc.deb_tgz:
            gbp.log.debug("Debian patch: %s" % dsc.deb_tgz)
    if dsc.epoch:
        gbp.log.debug("Epoch: %s" % dsc.epoch)


def move_tag_stamp(repo, format, version):
    "Move tag out of the way appending the current timestamp"
    old = repo.version_to_tag(format, version)
    timestamped = "%s~%s" % (version, int(time.time()))
    new = repo.version_to_tag(format, timestamped)
    repo.move_tag(old, new)


def disable_pristine_tar(options, reason):
    """Disable pristine tar if enabled"""
    if options.pristine_tar:
        gbp.log.info("%s: setting '--no-pristine-tar' option" % reason)
        options.pristine_tar = False


def build_parser(name):
    try:
        parser = GbpOptionParserDebian(command=os.path.basename(name), prefix='',
                                       usage='%prog [options] /path/to/package.dsc [target]')
    except GbpError as err:
        gbp.log.err(err)
        return None

    import_group = GbpOptionGroup(parser, "import options",
                                  "pristine-tar and filtering")
    tag_group = GbpOptionGroup(parser, "tag options",
                               "options related to git tag creation")
    branch_group = GbpOptionGroup(parser, "version and branch naming options",
                                  "version number and branch layout options")
    for group in [import_group, branch_group, tag_group]:
        parser.add_option_group(group)

    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    branch_group.add_config_file_option(option_name="debian-branch",
                                        dest="debian_branch")
    branch_group.add_config_file_option(option_name="upstream-branch",
                                        dest="upstream_branch")
    branch_group.add_boolean_config_file_option(option_name="create-missing-branches",
                                                dest="create_missing_branches")

    tag_group.add_boolean_config_file_option(option_name="sign-tags",
                                             dest="sign_tags")
    tag_group.add_config_file_option(option_name="keyid",
                                     dest="keyid")
    tag_group.add_config_file_option(option_name="debian-tag",
                                     dest="debian_tag")
    tag_group.add_config_file_option(option_name="upstream-tag",
                                     dest="upstream_tag")
    tag_group.add_option("--skip-debian-tag", dest="skip_debian_tag",
                         action="store_true", default=False,
                         help="Don't add a tag after importing the Debian patch")

    import_group.add_config_file_option(option_name="filter",
                                        dest="filters", action="append")
    import_group.add_boolean_config_file_option(option_name="pristine-tar",
                                                dest="pristine_tar")
    import_group.add_option("--allow-same-version", action="store_true",
                            dest="allow_same_version", default=False,
                            help="allow to import already imported version")
    import_group.add_boolean_config_file_option(option_name="author-is-committer",
                                                dest="author_committer")
    import_group.add_boolean_config_file_option(option_name="author-date-is-committer-date",
                                                dest="author_committer_date")
    import_group.add_boolean_config_file_option(option_name="allow-unauthenticated",
                                                dest="allow_unauthenticated")

    parser.add_config_file_option(option_name="repo-user", dest="repo_user",
                                  choices=['DEBIAN', 'GIT'])
    parser.add_config_file_option(option_name="repo-email", dest="repo_email",
                                  choices=['DEBIAN', 'GIT'])
    parser.add_option("--download", dest='download', action="store_true",
                      default=False, help="Ignored. Accepted for compatibility.")
    return parser


def parse_args(argv):
    parser = build_parser(argv[0])
    if not parser:
        return None, None

    (options, args) = parser.parse_args(argv[1:])
    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    if options.download:
        gbp.log.warn("Passing --download explicitly is deprecated.")

    return options, args


def is_download(pkg):
    """
    >>> is_download("http://foo.example.com/apackage.dsc")
    (True, 'http://foo.example.com/apackage.dsc')
    >>> is_download("apt://apackage/sid")
    (True, 'apackage/sid')
    >>> is_download("apt_1.0_amd64.dsc")
    (False, 'apt_1.0_amd64.dsc')
    >>> is_download("file:///foo/apackage.dsc")
    (False, '/foo/apackage.dsc')
    """
    if pkg.startswith('file://'):
        return (False, pkg[len('file://'):])
    elif pkg.startswith('apt://'):
        return (True, pkg[len('apt://'):])
    elif re.match("[a-z]{1,5}://", pkg):
        return (True, pkg)
    return (False, pkg)


def parse_all(argv):
    options, args = parse_args(argv)
    if not options:
        return None, None, None

    if len(args) == 1:
        pkg = args[0]
        target = None
    elif len(args) == 2:
        pkg = args[0]
        target = args[1]
    else:
        gbp.log.err("Need to give exactly one package to import. Try --help.")
        return None, None, None

    download, pkg = is_download(pkg)
    # honor options.download until removed
    options.download = download or options.download
    return options, pkg, target


def main(argv):
    dirs = dict(top=os.path.abspath(os.curdir))
    needs_repo = False
    ret = 0
    skipped = False

    options, pkg, target = parse_all(argv)
    if not options:
        return ExitCodes.parse_error

    try:
        try:
            repo = DebianGitRepository('.')
            is_empty = repo.is_empty()

            (clean, out) = repo.is_clean()
            if not clean and not is_empty:
                gbp.log.err("Repository has uncommitted changes, commit these first: ")
                raise GbpError(out)
        except GitRepositoryError:
            # no repo found, create one
            needs_repo = True
            is_empty = True

        if options.download:
            dsc = download_source(pkg,
                                  dirs=dirs,
                                  unauth=options.allow_unauthenticated)
        else:
            dsc = pkg

        src = DscFile.parse(dsc)
        if src.pkgformat not in ['1.0', '3.0']:
            raise GbpError("Importing %s source format not yet supported." % src.pkgformat)
        if options.verbose:
            print_dsc(src)

        if needs_repo:
            target = target or src.pkg
            if os.path.exists(target):
                raise GbpError("Directory '%s' already exists. If you want to import into it, "
                               "please change into this directory otherwise move it away first."
                               % target)
            gbp.log.info("No git repository found, creating one.")
            repo = DebianGitRepository.create(target)
            os.chdir(repo.path)
            repo_setup.set_user_name_and_email(options.repo_user, options.repo_email, repo)

        if repo.bare:
            disable_pristine_tar(options, "Bare repository")

        dirs['tmp'] = os.path.abspath(tempfile.mkdtemp(dir='..'))
        upstream = DebianUpstreamSource(src.tgz)
        upstream.unpack(dirs['tmp'], options.filters)
        for (component, tarball) in src.additional_tarballs.items():
            gbp.log.info("Found component tarball '%s'" % os.path.basename(tarball))
            unpack_component_tarball(upstream.unpacked, component, tarball, options.filters)

        format = [(options.upstream_tag, "Upstream"), (options.debian_tag, "Debian")][src.native]
        tag = repo.version_to_tag(format[0], src.upstream_version)
        msg = "%s version %s" % (format[1], src.upstream_version)

        if repo.find_version(options.debian_tag, src.version):
            gbp.log.warn("Version %s already imported." % src.version)
            if options.allow_same_version:
                gbp.log.info("Moving tag of version '%s' since import forced" % src.version)
                move_tag_stamp(repo, options.debian_tag, src.version)
            else:
                raise SkipImport

        if not repo.find_version(format[0], src.upstream_version):
            gbp.log.info("Tag %s not found, importing %s tarball" % (tag, format[1]))
            if is_empty:
                branch = None
            else:
                branch = [options.upstream_branch,
                          options.debian_branch][src.native]
                if not repo.has_branch(branch):
                    if options.create_missing_branches:
                        gbp.log.info("Creating missing branch '%s'" % branch)
                        repo.create_branch(branch)
                    else:
                        gbp.log.err(no_upstream_branch_msg % branch +
                                    "\nAlso check the --create-missing-branches option.")
                        raise GbpError

            if src.native:
                author = get_author_from_changelog(upstream.unpacked)
                committer = get_committer_from_author(author, options)
            else:
                author = committer = {}

            commit = repo.commit_dir(upstream.unpacked,
                                     "Import %s" % msg,
                                     branch,
                                     author=author,
                                     committer=committer)

            if not (src.native and options.skip_debian_tag):
                repo.create_tag(name=tag,
                                msg=msg,
                                commit=commit,
                                sign=options.sign_tags,
                                keyid=options.keyid)
            if not src.native:
                if is_empty:
                    repo.create_branch(options.upstream_branch, commit)
                if options.pristine_tar:
                    repo.create_pristinetar_commits(options.upstream_branch,
                                                    src.tgz,
                                                    src.additional_tarballs.items())
            if (not repo.has_branch(options.debian_branch) and
                    (is_empty or options.create_missing_branches)):
                repo.create_branch(options.debian_branch, commit)
        if not src.native:
            if src.diff or src.deb_tgz:
                apply_debian_patch(repo, upstream.unpacked, src, options,
                                   tag)
            else:
                gbp.log.warn("Didn't find a diff to apply.")
        if repo.get_branch() == options.debian_branch or is_empty:
            # Update HEAD if we modified the checked out branch
            repo.force_head(options.debian_branch, hard=True)
    except KeyboardInterrupt:
        ret = 1
        gbp.log.err("Interrupted. Aborting.")
    except gbpc.CommandExecFailed:
        ret = 1
    except GitRepositoryError as msg:
        gbp.log.err("Git command failed: %s" % msg)
        ret = 1
    except GbpError as err:
        if str(err):
            gbp.log.err(err)
        ret = 1
    except SkipImport:
        skipped = True
    finally:
        os.chdir(dirs['top'])

    for d in ['tmp', 'download']:
        if d in dirs:
            gbpc.RemoveTree(dirs[d])()

    if not ret and not skipped:
        gbp.log.info("Version '%s' imported under '%s'" % (src.version, repo.path))
    return ret


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
