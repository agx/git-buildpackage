# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007,2011,2012 Guido Guenther <agx@sigxcpu.org>
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
"""Import a Debian source package into a git repository"""

import ConfigParser
import sys
import re
import os
import shutil
import tempfile
import glob
import pipes
import time
import gbp.command_wrappers as gbpc
from gbp.pkg import UpstreamSource
from gbp.deb import  parse_dsc
from gbp.deb.git import (DebianGitRepository, GitRepositoryError)
from gbp.deb.changelog import ChangeLog
from gbp.git import rfc822_date_to_git
from gbp.git.modifier import GitModifier
from gbp.config import (GbpOptionParserDebian, GbpOptionGroup,
                        no_upstream_branch_msg)
from gbp.errors import GbpError
import gbp.log

class SkipImport(Exception):
    pass


def download_source(pkg, dirs, unauth):
    opts = [ '--download-only' ]
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
    dsc = glob.glob(os.path.join(dirs['download'], '*.dsc'))[0]
    return dsc


def apply_patch(diff):
    "Apply patch to a source tree"
    pipe = pipes.Template()
    pipe.prepend('gunzip -c %s' % diff,  '.-')
    pipe.append('patch -p1 --quiet', '-.')
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


def apply_debian_patch(repo, unpack_dir, src, options, parents):
    """apply the debian patch and tag appropriately"""
    try:
        os.chdir(unpack_dir)

        if src.diff and not apply_patch(src.diff):
            raise GbpError

        if src.deb_tgz and not apply_deb_tgz(src.deb_tgz):
            raise GbpError

        if os.path.exists('debian/rules'):
            os.chmod('debian/rules', 0755)
        os.chdir(repo.path)

        author = get_author_from_changelog(unpack_dir)
        committer = get_committer_from_author(author, options)
        commit = repo.commit_dir(unpack_dir,
                                 "Imported Debian patch %s" % src.version,
                                 branch = options.debian_branch,
                                 other_parents = parents,
                                 author=author,
                                 committer=committer)
        repo.create_tag(repo.version_to_tag(options.debian_tag, src.version),
                        msg="Debian release %s" % src.version,
                        commit=commit,
                        sign=options.sign_tags,
                        keyid=options.keyid)
    except (gbpc.CommandExecFailed, GitRepositoryError):
        gbp.log.err("Failed to import Debian package")
        raise GbpError
    finally:
        os.chdir(repo.path)


def print_dsc(dsc):
    if dsc.native:
        gbp.log.debug("Debian Native Package %s")
        gbp.log.debug("Version: %s" % dsc.upstream_version)
        gbp.log.debug("Debian tarball: %s" % dsc.tgz)
    else:
        gbp.log.debug("Upstream version: %s" % dsc.upstream_version)
        gbp.log.debug("Debian version: %s" % dsc.debian_version)
        gbp.log.debug("Upstream tarball: %s" % dsc.tgz)
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


def set_bare_repo_options(options):
    """Modify options for import into a bare repository"""
    if options.pristine_tar:
        gbp.log.info("Bare repository: setting %s option"
                      % (["", " '--no-pristine-tar'"][options.pristine_tar], ))
        options.pristine_tar = False


def parse_args(argv):
    try:
        parser = GbpOptionParserDebian(command=os.path.basename(argv[0]), prefix='',
                                       usage='%prog [options] /path/to/package.dsc')
    except ConfigParser.ParsingError as err:
        gbp.log.err(err)
        return None, None

    import_group = GbpOptionGroup(parser, "import options",
                      "pristine-tar and filtering")
    tag_group = GbpOptionGroup(parser, "tag options",
                      "options related to git tag creation")
    branch_group = GbpOptionGroup(parser, "version and branch naming options",
                      "version number and branch layout options")

    for group in [import_group, branch_group, tag_group ]:
        parser.add_option_group(group)

    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_option("--download", action="store_true", dest="download", default=False,
                      help="download source package")
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

    (options, args) = parser.parse_args(argv[1:])
    gbp.log.setup(options.color, options.verbose)
    return options, args


def main(argv):
    dirs = dict(top=os.path.abspath(os.curdir))
    needs_repo = False
    ret = 0
    skipped = False
    parents = None

    options, args = parse_args(argv)

    try:
        if len(args) != 1:
            gbp.log.err("Need to give exactly one package to import. Try --help.")
            raise GbpError
        else:
            pkg = args[0]
            if options.download:
                dsc = download_source(pkg,
                                      dirs=dirs,
                                      unauth=options.allow_unauthenticated)
            else:
                dsc = pkg

            src = parse_dsc(dsc)
            if src.pkgformat not in [ '1.0', '3.0' ]:
                raise GbpError("Importing %s source format not yet supported." % src.pkgformat)
            if options.verbose:
                print_dsc(src)

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

            if needs_repo:
                gbp.log.info("No git repository found, creating one.")
                repo = DebianGitRepository.create(src.pkg)
                os.chdir(repo.path)

            if repo.bare:
                set_bare_repo_options(options)

            dirs['tmp'] = os.path.abspath(tempfile.mkdtemp(dir='..'))
            upstream = UpstreamSource(src.tgz)
            upstream.unpack(dirs['tmp'], options.filters)

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
                                         "Imported %s" % msg,
                                         branch,
                                         author=author,
                                         committer=committer)

                repo.create_tag(name=tag,
                                msg=msg,
                                commit=commit,
                                sign=options.sign_tags,
                                keyid=options.keyid)
                if not src.native:
                    if is_empty:
                        repo.create_branch(options.upstream_branch, commit)
                    if options.pristine_tar:
                        repo.pristine_tar.commit(src.tgz, options.upstream_branch)
                    parents = [ options.upstream_branch ]
                if is_empty and not repo.has_branch(options.debian_branch):
                    repo.create_branch(options.debian_branch, commit)
            if not src.native:
                if src.diff or src.deb_tgz:
                    apply_debian_patch(repo, upstream.unpacked, src, options, parents)
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
        if len(err.__str__()):
            gbp.log.err(err)
        ret = 1
    except SkipImport:
        skipped = True
    finally:
        os.chdir(dirs['top'])

    for d in [ 'tmp', 'download' ]:
        if dirs.has_key(d):
            gbpc.RemoveTree(dirs[d])()

    if not ret and not skipped:
        gbp.log.info("Version '%s' imported under '%s'" % (src.version, src.pkg))
    return ret

if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
