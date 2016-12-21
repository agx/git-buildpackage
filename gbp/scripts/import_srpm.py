# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007,2011,2016 Guido Guenther <agx@sigxcpu.org>
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
"""Import an RPM source package into a Git repository"""

import sys
import re
import os
import glob
import time
import shutil
import errno
from six.moves.urllib.request import urlopen
from six.moves import urllib

import gbp.command_wrappers as gbpc
from gbp.tmpfile import init_tmpdir, del_tmpdir, tempfile
from gbp.rpm import (parse_srpm, guess_spec, SpecFile, NoSpecError,
                     RpmUpstreamSource, compose_version_str, filter_version)
from gbp.rpm.git import (RpmGitRepository, GitRepositoryError)
from gbp.git.modifier import GitModifier
from gbp.config import (GbpOptionParserRpm, GbpOptionGroup,
                        no_upstream_branch_msg)
from gbp.errors import GbpError
from gbp.scripts.common import ExitCodes
from gbp.scripts.common import repo_setup
import gbp.log
from gbp.pkg import parse_archive_filename

no_packaging_branch_msg = """
Repository does not have branch '%s' for packaging/distribution sources.
You need to reate it or use --packaging-branch to specify it.
"""


class SkipImport(Exception):
    """Nothing imported"""
    pass


def download_file(target_dir, url):
    """Download a remote file"""
    gbp.log.info("Downloading '%s'..." % url)
    try:
        urlobj = urlopen(url)
        local_fn = os.path.join(target_dir, os.path.basename(url))
        with open(local_fn, "wb") as local_file:
            local_file.write(urlobj.read())
    except urllib.error.HTTPError as err:
        raise GbpError("Download failed: %s" % err)
    except urllib.error.URLError as err:
        raise GbpError("Download failed: %s" % err.reason)
    return local_fn


def download_source(pkg):
    """Download package from a remote location"""
    if re.match(r'[a-z]{1,5}://', pkg):
        mode = 'python urllib'
    else:
        mode = 'yumdownloader'

    tmpdir = tempfile.mkdtemp(prefix='download_')
    gbp.log.info("Trying to download '%s' using '%s'..." % (pkg, mode))
    if mode == 'yumdownloader':
        gbpc.RunAtCommand('yumdownloader',
                          ['--source', '--destdir=', '.', pkg],
                          shell=False)(dir=tmpdir)
    else:
        download_file(tmpdir, pkg)
    srpm = glob.glob(os.path.join(tmpdir, '*.src.rpm'))[0]
    return srpm


def committer_from_author(author, options):
    """Get committer info based on options"""
    committer = GitModifier()
    if options.author_is_committer:
        committer.name = author.name
        committer.email = author.email
    return committer


def move_tag_stamp(repo, tag_format, tag_str_fields):
    "Move tag out of the way appending the current timestamp"
    old = repo.version_to_tag(tag_format, tag_str_fields)
    new = repo.version_to_tag('%s~%d' % (tag_format, int(time.time())),
                              tag_str_fields)
    repo.move_tag(old, new)


def set_bare_repo_options(options):
    """Modify options for import into a bare repository"""
    if options.pristine_tar:
        gbp.log.info("Bare repository: setting %s option '--no-pristine-tar'")
        options.pristine_tar = False


def force_to_branch_head(repo, branch):
    """Checkout branch and reset --hard"""
    if repo.get_branch() == branch:
        # Update HEAD if we modified the checked out branch
        repo.force_head(branch, hard=True)
    # Checkout packaging branch
    repo.set_branch(branch)


def build_parser(name):
    """Construct command line parser"""
    try:
        parser = GbpOptionParserRpm(command=os.path.basename(name),
                                    prefix='',
                                    usage='%prog [options] /path/to/package'
                                          '.src.rpm [target]')
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

    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      default=False, help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color",
                                  type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    parser.add_config_file_option(option_name="tmp-dir", dest="tmp_dir")
    parser.add_config_file_option(option_name="vendor", action="store",
                                  dest="vendor")
    parser.add_option("--download", action="store_true", dest="download",
                      default=False, help="download source package")
    branch_group.add_config_file_option(option_name="packaging-branch",
                                        dest="packaging_branch")
    branch_group.add_config_file_option(option_name="upstream-branch",
                                        dest="upstream_branch")
    branch_group.add_boolean_config_file_option(
        option_name="create-missing-branches",
        dest="create_missing_branches")
    branch_group.add_option("--orphan-packaging", action="store_true",
                            dest="orphan_packaging", default=False,
                            help="The packaging branch doesn't base on upstream")
    branch_group.add_option("--native", action="store_true",
                            dest="native", default=False,
                            help="This is a dist native package, no separate "
                            "upstream branch")

    tag_group.add_boolean_config_file_option(option_name="sign-tags",
                                             dest="sign_tags")
    tag_group.add_config_file_option(option_name="keyid",
                                     dest="keyid")
    tag_group.add_config_file_option(option_name="packaging-tag",
                                     dest="packaging_tag")
    tag_group.add_config_file_option(option_name="upstream-tag",
                                     dest="upstream_tag")

    import_group.add_config_file_option(option_name="filter",
                                        dest="filters", action="append")
    import_group.add_boolean_config_file_option(option_name="pristine-tar",
                                                dest="pristine_tar")
    import_group.add_option("--allow-same-version", action="store_true",
                            dest="allow_same_version", default=False,
                            help="allow to import already imported version")
    import_group.add_boolean_config_file_option(
        option_name="author-is-committer",
        dest="author_is_committer")
    import_group.add_config_file_option(option_name="packaging-dir",
                                        dest="packaging_dir")

    parser.add_config_file_option(option_name="repo-user", dest="repo_user",
                                  choices=['DEBIAN', 'GIT'])
    parser.add_config_file_option(option_name="repo-email", dest="repo_email",
                                  choices=['DEBIAN', 'GIT'])
    return parser


def parse_args(argv):
    """Parse commandline arguments"""
    parser = build_parser(argv[0])
    if not parser:
        return None, None

    (options, args) = parser.parse_args(argv[1:])
    gbp.log.setup(options.color, options.verbose, options.color_scheme)
    return options, args


def main(argv):
    """Main function of the git-import-srpm script"""
    dirs = dict(top=os.path.abspath(os.curdir))

    ret = 0
    skipped = False

    options, args = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    if len(args) == 1:
        srpm = args[0]
        target = None
    elif len(args) == 2:
        srpm = args[0]
        target = args[1]
    else:
        gbp.log.err("Need to give exactly one package to import. Try --help.")
        return 1
    try:
        dirs['tmp_base'] = init_tmpdir(options.tmp_dir, 'import-srpm_')
    except GbpError as err:
        gbp.log.err(err)
        return 1
    try:
        if options.download:
            srpm = download_source(srpm)

        # Real srpm, we need to unpack, first
        true_srcrpm = False
        if not os.path.isdir(srpm) and not srpm.endswith(".spec"):
            src = parse_srpm(srpm)
            true_srcrpm = True
            dirs['pkgextract'] = tempfile.mkdtemp(prefix='pkgextract_')
            gbp.log.info("Extracting src rpm to '%s'" % dirs['pkgextract'])
            src.unpack(dirs['pkgextract'])
            preferred_spec = src.name + '.spec'
            srpm = dirs['pkgextract']
        elif os.path.isdir(srpm):
            preferred_spec = os.path.basename(srpm.rstrip('/')) + '.spec'
        else:
            preferred_spec = None

        # Find and parse spec file
        if os.path.isdir(srpm):
            gbp.log.debug("Trying to import an unpacked srpm from '%s'" % srpm)
            dirs['src'] = os.path.abspath(srpm)
            spec = guess_spec(srpm, True, preferred_spec)
        else:
            gbp.log.debug("Trying to import an srpm from '%s' with spec "
                          "file '%s'" % (os.path.dirname(srpm), srpm))
            dirs['src'] = os.path.abspath(os.path.dirname(srpm))
            spec = SpecFile(srpm)

        # Check the repository state
        try:
            repo = RpmGitRepository('.')
            is_empty = repo.is_empty()

            (clean, out) = repo.is_clean()
            if not clean and not is_empty:
                gbp.log.err("Repository has uncommitted changes, commit "
                            "these first: ")
                raise GbpError(out)

        except GitRepositoryError:
            gbp.log.info("No git repository found, creating one.")
            is_empty = True
            target = target or spec.name
            repo = RpmGitRepository.create(target)
            os.chdir(repo.path)
            repo_setup.set_user_name_and_email(options.repo_user, options.repo_email, repo)

        if repo.bare:
            set_bare_repo_options(options)

        # Create more tempdirs
        dirs['origsrc'] = tempfile.mkdtemp(prefix='origsrc_')
        dirs['packaging_base'] = tempfile.mkdtemp(prefix='packaging_')
        dirs['packaging'] = os.path.join(dirs['packaging_base'],
                                         options.packaging_dir)
        try:
            os.mkdir(dirs['packaging'])
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise

        if true_srcrpm:
            # For true src.rpm we just take everything
            files = os.listdir(dirs['src'])
        else:
            # Need to copy files to the packaging directory given by caller
            files = [os.path.basename(patch.path)
                     for patch in spec.patchseries(unapplied=True, ignored=True)]
            for filename in spec.sources().values():
                files.append(os.path.basename(filename))
            files.append(os.path.join(spec.specdir, spec.specfile))
        # Don't copy orig source archive, though
        if spec.orig_src and spec.orig_src['filename'] in files:
            files.remove(spec.orig_src['filename'])

        for fname in files:
            fpath = os.path.join(dirs['src'], fname)
            if os.path.exists(fpath):
                shutil.copy2(fpath, dirs['packaging'])
            else:
                gbp.log.err("File '%s' listed in spec not found" % fname)
                raise GbpError

        # Unpack orig source archive
        if spec.orig_src:
            orig_tarball = os.path.join(dirs['src'], spec.orig_src['filename'])
            sources = RpmUpstreamSource(orig_tarball)
            sources.unpack(dirs['origsrc'], options.filters)
        else:
            sources = None

        tag_str_fields = dict(spec.version, vendor=options.vendor.lower())
        if options.native:
            src_tag_format = options.packaging_tag
            src_tag = repo.version_to_tag(src_tag_format, tag_str_fields)
            upstream_tag = src_tag
            upstream_str_fields = tag_str_fields
        else:
            src_tag_format = options.upstream_tag
            src_tag = repo.version_to_tag(src_tag_format, tag_str_fields)
            upstream_str_fields = filter_version(tag_str_fields, 'release', 'epoch')
            upstream_tag = repo.version_to_tag(src_tag_format, upstream_str_fields)

        ver_str = compose_version_str(spec.version)

        if repo.find_version(options.packaging_tag, tag_str_fields):
            gbp.log.warn("Version %s already imported." % ver_str)
            if options.allow_same_version:
                gbp.log.info("Moving tag of version '%s' since import forced" %
                             ver_str)
                move_tag_stamp(repo, options.packaging_tag, tag_str_fields)
            else:
                raise SkipImport

        if is_empty:
            options.create_missing_branches = True

        # Determine author and committer info, currently same info is used
        # for both sources and packaging files
        author = None
        if spec.packager:
            match = re.match(r'(?P<name>.*[^ ])\s*<(?P<email>\S*)>',
                             spec.packager.strip())
            if match:
                author = GitModifier(match.group('name'), match.group('email'))
        if not author:
            author = GitModifier()
            gbp.log.debug("Couldn't determine packager info")
        committer = committer_from_author(author, options)

        # Import sources
        if sources:
            src_commit = repo.find_version(src_tag_format, upstream_str_fields)
            if not src_commit:
                gbp.log.info("Tag %s not found, importing sources" % src_tag)

                branch = [options.upstream_branch,
                          options.packaging_branch][options.native]
                if not repo.has_branch(branch):
                    if options.create_missing_branches:
                        gbp.log.info("Will create missing branch '%s'" %
                                     branch)
                    else:
                        gbp.log.err(no_upstream_branch_msg % branch + "\n"
                                    "Also check the --create-missing-branches option.")
                        raise GbpError
                src_vendor = "Native" if options.native else "Upstream"
                msg = "%s version %s" % (src_vendor, spec.upstreamversion)
                src_commit = repo.commit_dir(sources.unpacked,
                                             "Import %s" % msg,
                                             branch,
                                             author=author,
                                             committer=committer,
                                             create_missing_branch=options.create_missing_branches)
                repo.create_tag(name=src_tag if options.native else upstream_tag,
                                msg=msg,
                                commit=src_commit,
                                sign=options.sign_tags,
                                keyid=options.keyid)

                if not options.native:
                    if options.pristine_tar:
                        archive_fmt = parse_archive_filename(orig_tarball)[1]
                        if archive_fmt == 'tar':
                            repo.pristine_tar.commit(orig_tarball,
                                                     'refs/heads/%s' %
                                                     options.upstream_branch)
                        else:
                            gbp.log.warn('Ignoring pristine-tar, %s archives '
                                         'not supported' % archive_fmt)
        else:
            gbp.log.info("No orig source archive imported")

        # Import packaging files. For native packages we assume that also
        # packaging files are found in the source tarball
        if not options.native or not sources:
            gbp.log.info("Importing packaging files")
            branch = options.packaging_branch
            if not repo.has_branch(branch):
                if options.create_missing_branches:
                    gbp.log.info("Will create missing branch '%s'" % branch)
                else:
                    gbp.log.err(no_packaging_branch_msg % branch + "\n"
                                "Also check the --create-missing-branches "
                                "option.")
                    raise GbpError

            tag = repo.version_to_tag(options.packaging_tag, tag_str_fields)
            msg = "%s release %s" % (options.vendor, ver_str)

            if options.orphan_packaging or not sources:
                commit = repo.commit_dir(dirs['packaging_base'],
                                         "Import %s" % msg,
                                         branch,
                                         author=author,
                                         committer=committer,
                                         create_missing_branch=options.create_missing_branches)
            else:
                # Copy packaging files to the unpacked sources dir
                try:
                    pkgsubdir = os.path.join(sources.unpacked,
                                             options.packaging_dir)
                    os.mkdir(pkgsubdir)
                except OSError as err:
                    if err.errno != errno.EEXIST:
                        raise
                for fname in os.listdir(dirs['packaging']):
                    shutil.copy2(os.path.join(dirs['packaging'], fname),
                                 pkgsubdir)
                commit = repo.commit_dir(sources.unpacked,
                                         "Import %s" % msg,
                                         branch,
                                         other_parents=[src_commit],
                                         author=author,
                                         committer=committer,
                                         create_missing_branch=options.create_missing_branches)
                # Import patches on top of the source tree
                # (only for non-native packages with non-orphan packaging)
                force_to_branch_head(repo, options.packaging_branch)

            # Create packaging tag
            repo.create_tag(name=tag,
                            msg=msg,
                            commit=commit,
                            sign=options.sign_tags,
                            keyid=options.keyid)

        force_to_branch_head(repo, options.packaging_branch)

    except KeyboardInterrupt:
        ret = 1
        gbp.log.err("Interrupted. Aborting.")
    except gbpc.CommandExecFailed:
        ret = 1
    except GitRepositoryError as err:
        gbp.log.err("Git command failed: %s" % err)
        ret = 1
    except GbpError as err:
        if str(err):
            gbp.log.err(err)
        ret = 1
    except NoSpecError as err:
        gbp.log.err("Failed determine spec file: %s" % err)
        ret = 1
    except SkipImport:
        skipped = True
    finally:
        os.chdir(dirs['top'])
        del_tmpdir()

    if not ret and not skipped:
        gbp.log.info("Version '%s' imported under '%s'" % (ver_str, repo.path))
    return ret


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
