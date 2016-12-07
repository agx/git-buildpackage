# vim: set fileencoding=utf-8 :
#
# (C) 2006-2011,2015,2016 Guido Günther <agx@sigxcpu.org>
# (C) 2012-2015 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""Build an RPM package out of a Git repository"""

import os
import shutil
import sys

import gbp.log
import gbp.notifications
import gbp.rpm as rpm
from gbp.command_wrappers import Command, RunAtCommand, CommandExecFailed
from gbp.config import GbpOptionParserRpm, GbpOptionGroup
from gbp.errors import GbpError
from gbp.format import format_str
from gbp.pkg import compressor_opts
from gbp.rpm.git import GitRepositoryError, RpmGitRepository
from gbp.rpm.policy import RpmPkgPolicy
from gbp.tmpfile import init_tmpdir, del_tmpdir, tempfile
from gbp.scripts.common import ExitCodes
from gbp.scripts.common.buildpackage import (index_name, wc_name,
                                             git_archive_submodules,
                                             git_archive_single, dump_tree,
                                             write_wc, drop_index)
from gbp.scripts.pq_rpm import parse_spec


class GbpAutoGenerateError(GbpError):
    pass


def makedir(path):
    """Create directory"""
    try:
        if not os.path.exists(path):
            os.makedirs(path)
    except OSError as err:
        raise GbpError("Cannot create dir %s: %s" % (path, err))
    return path


def git_archive(repo, spec, output_dir, treeish, prefix, comp_level,
                with_submodules):
    "Create a compressed orig tarball in output_dir using git_archive"
    comp_opts = ''
    if spec.orig_src['compression']:
        comp_opts = compressor_opts[spec.orig_src['compression']][0]

    output = os.path.join(output_dir, spec.orig_src['filename'])

    # Remove extra slashes from prefix, will be added by git_archive_x funcs
    prefix = prefix.strip('/')
    try:
        if repo.has_submodules(treeish) and with_submodules:
            repo.update_submodules()
            git_archive_submodules(repo, treeish, output, prefix,
                                   spec.orig_src['compression'],
                                   comp_level, comp_opts,
                                   spec.orig_src['archive_fmt'])

        else:
            git_archive_single(treeish, output, prefix,
                               spec.orig_src['compression'], comp_level,
                               comp_opts, spec.orig_src['archive_fmt'])
    except (GitRepositoryError, CommandExecFailed) as e:
        gbp.log.err("Error generating submodules' archives: %s" % e)
        return False
    return True


def prepare_upstream_tarball(repo, spec, options, output_dir):
    """Make sure we have an upstream tarball"""
    # look in tarball_dir first, if found force a symlink to it
    orig_file = spec.orig_src['filename']
    if options.tarball_dir:
        gbp.log.debug("Looking for orig tarball '%s' at '%s'" %
                      (orig_file, options.tarball_dir))
        if not RpmPkgPolicy.symlink_orig(orig_file, options.tarball_dir,
                                         output_dir, force=True):
            gbp.log.info("Orig tarball '%s' not found at '%s'" %
                         (orig_file, options.tarball_dir))
        else:
            gbp.log.info("Orig tarball '%s' found at '%s'" %
                         (orig_file, options.tarball_dir))

    # build an orig unless the user forbids it, always build (and overwrite
    # pre-existing) if user forces it
    if options.force_create or (not options.no_create_orig and not
                                RpmPkgPolicy.has_orig(orig_file, output_dir)):
        if not pristine_tar_build_orig(repo, orig_file, output_dir, options):
            upstream_tree = git_archive_build_orig(repo, spec, output_dir,
                                                   options)
            if options.pristine_tar_commit:
                if repo.pristine_tar.has_commit(orig_file):
                    gbp.log.debug("%s already on pristine tar branch" %
                                  orig_file)
                else:
                    archive = os.path.join(output_dir, orig_file)
                    gbp.log.debug("Adding %s to pristine-tar branch" %
                                  archive)
                    repo.pristine_tar.commit(archive, upstream_tree)


def pristine_tar_build_orig(repo, orig_file, output_dir, options):
    """Build orig using pristine-tar"""
    if options.pristine_tar:
        if not repo.has_branch(repo.pristine_tar_branch):
            gbp.log.warn('Pristine-tar branch "%s" not found' %
                         repo.pristine_tar.branch)
        try:
            repo.pristine_tar.checkout(os.path.join(output_dir, orig_file))
            return True
        except CommandExecFailed:
            if options.pristine_tar_commit:
                gbp.log.debug("pristine-tar checkout failed, "
                              "will commit tarball due to "
                              "'--pristine-tar-commit'")
            elif not options.force_create:
                raise
    return False


def get_upstream_tree(repo, version, options):
    """Determine the upstream tree from the given options"""
    if options.upstream_tree.upper() == 'TAG':
        tag_str_fields = {'upstreamversion': version,
                          'version': version}
        upstream_tree = repo.version_to_tag(options.upstream_tag,
                                            tag_str_fields)
    elif options.upstream_tree.upper() == 'BRANCH':
        if not repo.has_branch(options.upstream_branch):
            raise GbpError("%s is not a valid branch" % options.upstream_branch)
        upstream_tree = options.upstream_branch
    else:
        upstream_tree = get_tree(repo, options.upstream_tree)
    if not repo.has_treeish(upstream_tree):
        raise GbpError('Invalid upstream treeish %s' % upstream_tree)
    return upstream_tree


def get_tree(repo, tree_name):
    """
    Get/create a tree-ish to be used for exporting and diffing. Accepts
    special keywords for git index and working copies.
    """
    try:
        if tree_name == index_name:
            # Write a tree of the index
            tree = repo.write_tree()
        elif tree_name == wc_name:
            # Write a tree of the working copy
            tree = write_wc(repo)
        else:
            tree = tree_name
    except GitRepositoryError as err:
        raise GbpError(err)
    if not repo.has_treeish(tree):
        raise GbpError('Invalid treeish object %s' % tree)

    return tree


def get_current_branch(repo):
    """Get the currently checked-out branch"""
    try:
        branch = repo.get_branch()
    except GitRepositoryError:
        branch = None
    return branch


def git_archive_build_orig(repo, spec, output_dir, options):
    """
    Build orig tarball using git-archive

    @param repo: our git repository
    @type repo: L{RpmGitRepository}
    @param spec: spec file of the package
    @type spec: L{SpecFile}
    @param output_dir: where to put the tarball
    @type output_dir: C{Str}
    @param options: the parsed options
    @type options: C{dict} of options
    @return: the tree we built the tarball from
    @rtype: C{str}
    """
    try:
        orig_prefix = spec.orig_src['prefix']
        upstream_tree = get_upstream_tree(repo, spec.upstreamversion, options)
        gbp.log.info("%s does not exist, creating from '%s'" %
                     (spec.orig_src['filename'], upstream_tree))
        if spec.orig_src['compression']:
            gbp.log.debug("Building upstream source archive with compression "
                          "'%s -%s'" % (spec.orig_src['compression'],
                                        options.comp_level))
        if not git_archive(repo, spec, output_dir, upstream_tree,
                           orig_prefix, options.comp_level,
                           options.with_submodules):
            raise GbpError("Cannot create upstream tarball at '%s'" %
                           output_dir)
    except (GitRepositoryError, GbpError) as err:
        raise GbpAutoGenerateError(str(err))
    return upstream_tree


def is_native(repo, options):
    """Determine whether a package is native or non-native"""
    if options.native.is_auto():
        if repo.has_branch(options.upstream_branch):
            return False
        # Check remotes, too
        for remote_branch in repo.get_remote_branches():
            remote, branch = remote_branch.split('/', 1)
            if branch == options.upstream_branch:
                gbp.log.debug("Found upstream branch '%s' from remote '%s'" %
                              (remote, branch))
                return False
        return True

    return options.native.is_on()


def setup_builder(options, builder_args):
    """Setup args and options for builder script"""
    if options.builder == 'rpmbuild':
        if len(builder_args) == 0:
            builder_args.append('-ba')
        builder_args.extend([
            '--define "_topdir %s"' % os.path.abspath(options.export_dir),
            '--define "_specdir %%_topdir/%s"' % options.export_specdir,
            '--define "_sourcedir %%_topdir/%s"' % options.export_sourcedir])


def packaging_tag_data(repo, commit, name, version, options):
    """Compose packaging tag name and msg"""
    version_dict = dict(version, version=rpm.compose_version_str(version))

    # Compose tag name and message
    tag_name_fields = dict(version_dict, vendor=options.vendor.lower())
    tag_name = repo.version_to_tag(options.packaging_tag, tag_name_fields)

    tag_msg = format_str(options.packaging_tag_msg,
                         dict(version_dict, pkg=name,
                              vendor=options.vendor))
    return (tag_name, tag_msg)


def setup_mock(options):
    """setup everything to use gbp-builder-mock"""
    if options.use_mock:
        options.builder = '/usr/share/git-buildpackage/gbp-builder-mock'
        options.cleaner = '/bin/true'
        os.environ['GBP_BUILDER_MOCK_DIST'] = options.mock_dist
        if options.mock_arch:
            os.environ['GBP_BUILDER_MOCK_ARCH'] = options.mock_arch
        if options.mock_root:
            os.environ['GBP_BUILDER_MOCK_ROOT'] = options.mock_root
        os.environ['GBP_BUILDER_MOCK_EXPORT_DIR'] = options.export_dir
        if options.mock_options:
            os.environ['GBP_BUILDER_MOCK_OPTIONS'] = options.mock_options


def create_packaging_tag(repo, commit, name, version, options):
    """Create a packaging/release Git tag"""
    tag_name, tag_msg = packaging_tag_data(repo, commit, name, version, options)

    if options.retag and repo.has_tag(tag_name):
        repo.delete_tag(tag_name)
    repo.create_tag(name=tag_name, msg=tag_msg, sign=options.sign_tags,
                    keyid=options.keyid, commit=commit)
    return tag_name


def disable_hooks(options):
    """Disable all hooks (except for builder)"""
    for hook in ['cleaner', 'postexport', 'prebuild', 'postbuild', 'posttag']:
        if getattr(options, hook):
            gbp.log.info("Disabling '%s' hook" % hook)
            setattr(options, hook, '')


def build_parser(name, prefix=None, git_treeish=None):
    """Construct config/option parser"""
    try:
        parser = GbpOptionParserRpm(command=os.path.basename(name),
                                    prefix=prefix)
    except GbpError as err:
        gbp.log.err(err)
        return None

    tag_group = GbpOptionGroup(parser, "tag options",
                               "options related to git tag creation")
    branch_group = GbpOptionGroup(parser, "branch options",
                                  "branch layout options")
    cmd_group = GbpOptionGroup(parser, "external command options",
                               "how and when to invoke external commands and hooks")
    orig_group = GbpOptionGroup(parser, "orig tarball options",
                                "options related to the creation of the orig tarball")
    export_group = GbpOptionGroup(parser, "export build-tree options",
                                  "alternative build tree related options")
    parser.add_option_group(tag_group)
    parser.add_option_group(orig_group)
    parser.add_option_group(branch_group)
    parser.add_option_group(cmd_group)
    parser.add_option_group(export_group)

    parser.add_boolean_config_file_option(option_name="ignore-new",
                                          dest="ignore_new")
    parser.add_option("--git-verbose", action="store_true", dest="verbose",
                      default=False, help="verbose command execution")
    parser.add_config_file_option(option_name="tmp-dir", dest="tmp_dir")
    parser.add_config_file_option(option_name="color", dest="color",
                                  type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    parser.add_config_file_option(option_name="notify", dest="notify",
                                  type='tristate')
    parser.add_config_file_option(option_name="vendor", action="store",
                                  dest="vendor")
    parser.add_config_file_option(option_name="native", dest="native",
                                  type='tristate')
    tag_group.add_option("--git-tag", action="store_true", dest="tag",
                         default=False,
                         help="create a tag after a successful build")
    tag_group.add_option("--git-tag-only", action="store_true", dest="tag_only",
                         default=False,
                         help="don't build, only tag and run the posttag hook")
    tag_group.add_option("--git-retag", action="store_true", dest="retag",
                         default=False, help="don't fail if the tag already exists")
    tag_group.add_boolean_config_file_option(option_name="sign-tags",
                                             dest="sign_tags")
    tag_group.add_config_file_option(option_name="keyid", dest="keyid")
    tag_group.add_config_file_option(option_name="packaging-tag",
                                     dest="packaging_tag")
    tag_group.add_config_file_option(option_name="packaging-tag-msg",
                                     dest="packaging_tag_msg")
    tag_group.add_config_file_option(option_name="upstream-tag",
                                     dest="upstream_tag")
    orig_group.add_config_file_option(option_name="upstream-tree",
                                      dest="upstream_tree")
    orig_group.add_boolean_config_file_option(option_name="pristine-tar",
                                              dest="pristine_tar")
    orig_group.add_boolean_config_file_option(option_name="pristine-tar-commit",
                                              dest="pristine_tar_commit")
    orig_group.add_config_file_option(option_name="force-create",
                                      dest="force_create", action="store_true",
                                      help="force creation of upstream source tarball")
    orig_group.add_config_file_option(option_name="no-create-orig",
                                      dest="no_create_orig", action="store_true",
                                      help="don't create upstream source tarball")
    orig_group.add_config_file_option(option_name="tarball-dir",
                                      dest="tarball_dir", type="path",
                                      help="location to look for external tarballs")
    orig_group.add_config_file_option(option_name="compression-level",
                                      dest="comp_level",
                                      help="Compression level, default is "
                                      "'%(compression-level)s'")
    branch_group.add_config_file_option(option_name="upstream-branch",
                                        dest="upstream_branch")
    branch_group.add_config_file_option(option_name="packaging-branch",
                                        dest="packaging_branch")
    branch_group.add_boolean_config_file_option(option_name="ignore-branch",
                                                dest="ignore_branch")
    branch_group.add_boolean_config_file_option(option_name="submodules",
                                                dest="with_submodules")
    cmd_group.add_config_file_option(option_name="builder", dest="builder",
                                     help="command to build the package, default is "
                                     "'%(builder)s'")
    cmd_group.add_config_file_option(option_name="cleaner", dest="cleaner",
                                     help="command to clean the working copy, default is "
                                     "'%(cleaner)s'")
    cmd_group.add_config_file_option(option_name="prebuild", dest="prebuild",
                                     help="command to run before a build, default is "
                                     "'%(prebuild)s'")
    cmd_group.add_config_file_option(option_name="postexport",
                                     dest="postexport",
                                     help="command to run after exporting the source tree, "
                                     "default is '%(postexport)s'")
    cmd_group.add_config_file_option(option_name="postbuild", dest="postbuild",
                                     help="hook run after a successful build, default is "
                                     "'%(postbuild)s'")
    cmd_group.add_config_file_option(option_name="posttag", dest="posttag",
                                     help="hook run after a successful tag operation, default "
                                     "is '%(posttag)s'")
    cmd_group.add_boolean_config_file_option(option_name="mock", dest="use_mock")
    cmd_group.add_config_file_option(option_name="dist", dest="mock_dist")
    cmd_group.add_config_file_option(option_name="arch", dest="mock_arch")
    cmd_group.add_config_file_option(option_name="mock-root", dest="mock_root")
    cmd_group.add_config_file_option(option_name="mock-options", dest="mock_options")
    cmd_group.add_boolean_config_file_option(option_name="hooks", dest="hooks")
    export_group.add_option("--git-no-build", action="store_true",
                            dest="no_build",
                            help="Don't run builder or the associated hooks")
    export_group.add_config_file_option(option_name="export-dir",
                                        dest="export_dir", type="path",
                                        help="Build topdir, also export the sources under "
                                        "EXPORT_DIR, default is '%(export-dir)s'")
    export_group.add_config_file_option(option_name="export-specdir",
                                        dest="export_specdir", type="path")
    export_group.add_config_file_option(option_name="export-sourcedir",
                                        dest="export_sourcedir", type="path")
    export_group.add_config_file_option("export", dest="export",
                                        metavar="TREEISH",
                                        help="export treeish object TREEISH, default is "
                                        "'%(export)s'")
    export_group.add_config_file_option(option_name="packaging-dir",
                                        dest="packaging_dir")
    export_group.add_config_file_option(option_name="spec-file",
                                        dest="spec_file")
    return parser


def parse_args(argv, prefix, git_treeish=None):
    """Parse config and command line arguments"""
    args = [arg for arg in argv[1:] if arg.find('--%s' % prefix) == 0]
    builder_args = [arg for arg in argv[1:] if arg.find('--%s' % prefix) == -1]

    # We handle these although they don't have a --git- prefix
    for arg in ["--help", "-h", "--version"]:
        if arg in builder_args:
            args.append(arg)

    parser = build_parser(argv[0], prefix=prefix, git_treeish=git_treeish)
    if not parser:
        return None, None, None
    options, args = parser.parse_args(args)

    gbp.log.setup(options.color, options.verbose, options.color_scheme)
    if not options.hooks:
        disable_hooks(options)
    if options.retag:
        if not options.tag and not options.tag_only:
            gbp.log.err("'--%sretag' needs either '--%stag' or '--%stag-only'" %
                        (prefix, prefix, prefix))
            return None, None, None

    return options, args, builder_args


def main(argv):
    """Entry point for gbp-buildpackage-rpm"""
    retval = 0
    prefix = "git-"
    spec = None

    options, gbp_args, builder_args = parse_args(argv, prefix)

    if not options:
        return ExitCodes.parse_error

    try:
        repo = RpmGitRepository(os.path.curdir)
    except GitRepositoryError:
        gbp.log.err("%s is not a git repository" % (os.path.abspath('.')))
        return 1

    # Determine tree-ish to be exported
    try:
        tree = get_tree(repo, options.export)
    except GbpError as err:
        gbp.log.err('Failed to determine export treeish: %s' % err)
        return 1
    # Re-parse config options with using the per-tree config file(s) from the
    # exported tree-ish
    options, gbp_args, builder_args = parse_args(argv, prefix, tree)

    branch = get_current_branch(repo)

    try:
        init_tmpdir(options.tmp_dir, prefix='buildpackage-rpm_')

        tree = get_tree(repo, options.export)
        spec = parse_spec(options, repo, treeish=tree)

        Command(options.cleaner, shell=True)()
        if not options.ignore_new:
            ret, out = repo.is_clean()
            if not ret:
                gbp.log.err("You have uncommitted changes in your source tree:")
                gbp.log.err(out)
                raise GbpError("Use --git-ignore-new to ignore.")

        if not options.ignore_new and not options.ignore_branch:
            if branch != options.packaging_branch:
                gbp.log.err("You are not on branch '%s' but on '%s'" %
                            (options.packaging_branch, branch))
                raise GbpError("Use --git-ignore-branch to ignore or "
                               "--git-packaging-branch to set the branch name.")

        # Dump from git to a temporary directory:
        packaging_tree = '%s:%s' % (tree, options.packaging_dir)
        dump_dir = tempfile.mkdtemp(prefix='packaging_')
        gbp.log.debug("Dumping packaging files to '%s'" % dump_dir)
        if not dump_tree(repo, dump_dir, packaging_tree, False, False):
            raise GbpError
        # Re-parse spec from dump dir to get version etc.
        spec = rpm.SpecFile(os.path.join(dump_dir, spec.specfile))

        if not options.tag_only:
            # Setup builder opts
            setup_builder(options, builder_args)
            if options.use_mock:
                setup_mock(options)

            # Prepare final export dirs
            export_dir = makedir(options.export_dir)
            source_dir = makedir(os.path.join(export_dir,
                                 options.export_sourcedir))
            spec_dir = makedir(os.path.join(export_dir, options.export_specdir))

            # Move packaging files to final export dir
            gbp.log.debug("Exporting packaging files from '%s' to '%s'" %
                          (dump_dir, export_dir))
            for fname in os.listdir(dump_dir):
                src = os.path.join(dump_dir, fname)
                if fname == spec.specfile:
                    dst = os.path.join(spec_dir, fname)
                else:
                    dst = os.path.join(source_dir, fname)
                try:
                    shutil.copy2(src, dst)
                except IOError as err:
                    raise GbpError("Error exporting packaging files: %s" % err)
            spec.specdir = os.path.abspath(spec_dir)

            # Get/build the orig tarball
            if is_native(repo, options):
                if spec.orig_src and not options.no_create_orig:
                    # Just build source archive from the exported tree
                    gbp.log.info("Creating (native) source archive %s from '%s'"
                                 % (spec.orig_src['filename'], tree))
                    if spec.orig_src['compression']:
                        gbp.log.debug("Building source archive with "
                                      "compression '%s -%s'" %
                                      (spec.orig_src['compression'],
                                       options.comp_level))
                    orig_prefix = spec.orig_src['prefix']
                    if not git_archive(repo, spec, source_dir, tree,
                                       orig_prefix, options.comp_level,
                                       options.with_submodules):
                        raise GbpError("Cannot create source tarball at '%s'" %
                                       source_dir)
            # Non-native packages: create orig tarball from upstream
            elif spec.orig_src:
                prepare_upstream_tarball(repo, spec, options, source_dir)

            # Run postexport hook
            if options.postexport:
                RunAtCommand(options.postexport, shell=True,
                             extra_env={'GBP_GIT_DIR': repo.git_dir,
                                        'GBP_TMP_DIR': export_dir}
                             )(dir=export_dir)
            # Do actual build
            if not options.no_build and not options.tag_only:
                if options.prebuild:
                    RunAtCommand(options.prebuild, shell=True,
                                 extra_env={'GBP_GIT_DIR': repo.git_dir,
                                            'GBP_BUILD_DIR': export_dir}
                                 )(dir=export_dir)

                # Finally build the package:
                if options.builder.startswith("rpmbuild"):
                    builder_args.append(os.path.join(spec.specdir,
                                        spec.specfile))
                else:
                    builder_args.append(spec.specfile)
                RunAtCommand(options.builder, builder_args, shell=True,
                             extra_env={'GBP_BUILD_DIR': export_dir}
                             )(dir=export_dir)
                if options.postbuild:
                    changes = os.path.abspath("%s/%s.changes" % (source_dir,
                                                                 spec.name))
                    gbp.log.debug("Looking for changes file %s" % changes)
                    Command(options.postbuild, shell=True,
                            extra_env={'GBP_CHANGES_FILE': changes,
                                       'GBP_BUILD_DIR': export_dir})()

        # Tag (note: tags the exported version)
        if options.tag or options.tag_only:
            gbp.log.info("Tagging %s" % rpm.compose_version_str(spec.version))
            tag = create_packaging_tag(repo, tree, spec.name, spec.version,
                                       options)
            if options.posttag:
                sha = repo.rev_parse("%s^{}" % tag)
                Command(options.posttag, shell=True,
                        extra_env={'GBP_TAG': tag,
                                   'GBP_BRANCH': branch,
                                   'GBP_SHA1': sha})()
    except KeyboardInterrupt:
        retval = 1
        gbp.log.err("Interrupted. Aborting.")
    except CommandExecFailed:
        retval = 1
    except GitRepositoryError as err:
        gbp.log.err("Git command failed: %s" % err)
        retval = 1
    except GbpAutoGenerateError as err:
        if len(err.__str__()):
            gbp.log.err(err)
        retval = 2
    except GbpError as err:
        if len(err.__str__()):
            gbp.log.err(err)
        retval = 1
    finally:
        drop_index()
        del_tmpdir()

    if not options.tag_only:
        if spec and options.notify:
            summary = "Gbp-rpm %s" % ["failed", "successful"][not retval]
            message = ("Build of %s %s %s" % (spec.name,
                                              rpm.compose_version_str(spec.version),
                                              ["failed", "succeeded"][not retval]))
            if not gbp.notifications.notify(summary, message, options.notify):
                gbp.log.err("Failed to send notification")
                retval = 1

    return retval


if __name__ == '__main__':
    sys.exit(main(sys.argv))
