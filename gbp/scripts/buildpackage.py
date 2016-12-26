# vim: set fileencoding=utf-8 :
#
# (C) 2006-2016 Guido Günther <agx@sigxcpu.org>
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
"""Build a Debian package out of a Git repository"""

import errno
import os
import shutil
import sys
import time
import gbp.deb as du
from gbp.command_wrappers import (Command,
                                  RunAtCommand, CommandExecFailed,
                                  RemoveTree)
from gbp.config import (GbpOptionParserDebian, GbpOptionGroup)
from gbp.deb.git import (GitRepositoryError, DebianGitRepository)
from gbp.deb.source import DebianSource, DebianSourceError
from gbp.deb.format import DebianSourceFormat
from gbp.format import format_str
from gbp.git.vfs import GitVfs
from gbp.deb.upstreamsource import DebianUpstreamSource
from gbp.errors import GbpError
import gbp.log
import gbp.notifications
from gbp.scripts.common.buildpackage import (index_name, wc_name,
                                             git_archive_submodules,
                                             git_archive_single, dump_tree,
                                             write_wc, drop_index)
from gbp.scripts.common import ExitCodes
from gbp.scripts.common.hook import Hook
from gbp.pkg import compressor_opts, compressor_aliases, parse_archive_filename


# upstream tarball preparation
def git_archive(repo, cp, output_dir, treeish, comp_type, comp_level, with_submodules, component=None):
    "create a compressed orig tarball in output_dir using git_archive"
    try:
        comp_opts = compressor_opts[comp_type][0]
    except KeyError:
        raise GbpError("Unsupported compression type '%s'" % comp_type)

    output = os.path.join(output_dir, du.orig_file(cp, comp_type, component=component))
    prefix = "%s-%s" % (cp['Source'], cp['Upstream-Version'])

    try:
        if repo.has_submodules() and with_submodules:
            repo.update_submodules()
            git_archive_submodules(repo, treeish, output, prefix,
                                   comp_type, comp_level, comp_opts)

        else:
            git_archive_single(treeish, output, prefix,
                               comp_type, comp_level, comp_opts)
    except (GitRepositoryError, CommandExecFailed):
        gbp.log.err("Error generating submodules' archives")
        return False
    except OSError as e:
        gbp.log.err("Error creating %s: %s" % (output, str(e)))
        return False
    except GbpError:
        raise
    except Exception as e:
        gbp.log.err("Error creating %s: %s" % (output, str(e)))
        return False
    return True


def prepare_upstream_tarball(repo, cp, options, tarball_dir, output_dir):
    """
    Make sure we have an upstream tarball. This involves loooking in
    tarball_dir, symlinking or building it.
    """
    options.comp_type = guess_comp_type(repo,
                                        options.comp_type,
                                        cp,
                                        options.tarball_dir)

    orig_files = [du.orig_file(cp, options.comp_type)]
    if options.components:
        orig_files += [du.orig_file(cp, options.comp_type, c) for c in options.components]

    # look in tarball_dir first, if found force a symlink to it
    if options.tarball_dir:
        gbp.log.debug("Looking for orig tarballs '%s' at '%s'" % (", ".join(orig_files), tarball_dir))
        missing = du.DebianPkgPolicy.symlink_origs(orig_files, tarball_dir, output_dir, force=True)
        if missing:
            msg = "Tarballs '%s' not found at '%s'" % (", ".join(missing), tarball_dir)
        else:
            msg = "All Orig tarballs '%s' found at '%s'" % (", ".join(orig_files), tarball_dir)
        gbp.log.info(msg)
    if options.no_create_orig:
        return
    # Create tarball if missing or forced
    if not du.DebianPkgPolicy.has_origs(orig_files, output_dir) or options.force_create:
        if not pristine_tar_build_orig(repo, cp, output_dir, options):
            upstream_tree = git_archive_build_orig(repo, cp, output_dir, options)
            if options.pristine_tar_commit:
                pristine_tar_commit(repo, cp, options, output_dir, orig_files[0], upstream_tree)


def pristine_tar_commit(repo, cp, options, output_dir, orig_file, upstream_tree):
    if repo.pristine_tar.has_commit(cp.name,
                                    cp.upstream_version,
                                    options.comp_type):
        gbp.log.debug("%s already on pristine tar branch" %
                      orig_file)
    else:
        archive = os.path.join(output_dir, orig_file)
        gbp.log.debug("Adding %s to pristine-tar branch" %
                      archive)
        repo.pristine_tar.commit(archive, upstream_tree)


# Functions to handle export-dir
def write_tree(repo, options):
    """
    Write a tree of the index or working copy if necessary

    @param repo: the git repository we're acting on
    @type repo: L{GitRepository}
    @return: the sha1 of the tree
    @rtype: C{str}
    """
    if options.export_dir:
        if options.export == index_name:
            tree = repo.write_tree()
        elif options.export == wc_name:
            tree = write_wc(repo)
        else:
            tree = options.export
        if not repo.has_treeish(tree):
            raise GbpError("%s is not a valid treeish" % tree)
    else:
        tree = None
    return tree


def export_source(repo, tree, source, options, dest_dir, tarball_dir):
    """
    Export a version of the source tree when building in a separate directory

    @param repo: the git repository to export from
    @type repo: L{gbp.git.GitRepository}
    @param source: the source package
    @param options: options to apply
    @param dest_dir: where to export the source to
    @param tarball_dir: where to fetch the tarball from in overlay mode
    @returns: the temporary directory
    """
    # Extract orig tarball if git-overlay option is selected:
    if options.overlay:
        if source.is_native():
            raise GbpError("Cannot overlay Debian native package")
        extract_orig(os.path.join(tarball_dir,
                                  du.orig_file(source.changelog,
                                               options.comp_type)),
                     dest_dir)

    gbp.log.info("Exporting '%s' to '%s'" % (options.export, dest_dir))
    if not dump_tree(repo, dest_dir, tree, options.with_submodules):
        raise GbpError


def move_old_export(target):
    """move a build tree away if it exists"""
    try:
        os.mkdir(target)
    except OSError as e:
        if e.errno == errno.EEXIST:
            os.rename(target, "%s.obsolete.%s" % (target, time.time()))


def extract_orig(orig_tarball, dest_dir):
    """extract orig tarball to export dir before exporting from git"""
    gbp.log.info("Extracting %s to '%s'" % (os.path.basename(orig_tarball), dest_dir))

    move_old_export(dest_dir)
    upstream = DebianUpstreamSource(orig_tarball)
    upstream.unpack(dest_dir)

    # Check if tarball extracts into a single folder:
    if upstream.unpacked != dest_dir:
        # If it extracts a single folder, move its contents to dest_dir:
        gbp.log.debug("Moving %s to %s" % (upstream.unpacked, dest_dir))
        tmpdir = dest_dir + '.new'
        os.rename(upstream.unpacked, tmpdir)
        os.rmdir(dest_dir)
        os.rename(tmpdir, dest_dir)

    # Remove debian/ from unpacked upstream tarball in case of non 1.0 format
    underlay_debian_dir = os.path.join(dest_dir, 'debian')
    format_file = os.path.join('debian', 'source', 'format')
    if os.path.exists(underlay_debian_dir) and os.path.exists(format_file):
        format = DebianSourceFormat.parse_file(format_file)
        if format.version in ['2.0', '3.0']:
            gbp.log.info("Removing debian/ from unpacked upstream "
                         "source at %s" % underlay_debian_dir)
            shutil.rmtree(underlay_debian_dir)


def source_vfs(repo, options, tree):
    """Init source package info either from git or from working copy"""
    # FIXME: just init the correct vfs
    try:
        if tree:
            source = DebianSource(GitVfs(repo, tree))
        else:
            source = DebianSource('.')
            source.is_native()  # check early if this works
    except Exception as e:
        raise GbpError("Can't determine package type: %s" % e)
    return source


def prepare_output_dir(dir):
    """Prepare the directory where the build result will be put"""
    output_dir = dir
    if not dir:
        output_dir = '..'
    output_dir = os.path.abspath(output_dir)

    try:
        os.mkdir(output_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise GbpError("Cannot create output dir %s" % output_dir)
    return output_dir


def pristine_tar_build_orig(repo, cp, output_dir, options):
    """
    Build orig tarball using pristine-tar

    @returns: C{True} if tarball was build, C{False} otherwise
    """
    if options.pristine_tar:
        if not repo.has_branch(repo.pristine_tar_branch):
            gbp.log.warn('Pristine-tar branch "%s" not found' %
                         repo.pristine_tar.branch)

        # Make sure the upstream tree exists, it might not be there in
        # case of components since we don't keep a ref to it
        if options.components:
            try:
                upstream_tag = repo.version_to_tag(options.upstream_tag, cp.upstream_version)
                tree_name = "%s^{tree}" % upstream_tag
                repo.tree_drop_dirs(tree_name, options.components)
            except GitRepositoryError:
                raise GbpError("Couldn't find upstream tree '%s' to create "
                               "orig tarball via pristine-tar" % tree_name)

        try:
            repo.pristine_tar.checkout(cp.name,
                                       cp.upstream_version,
                                       options.comp_type,
                                       output_dir)
            for component in options.components:
                repo.pristine_tar.checkout(cp.name,
                                           cp.upstream_version,
                                           options.comp_type,
                                           output_dir,
                                           component=component)
            return True
        except CommandExecFailed:
            if options.pristine_tar_commit:
                gbp.log.debug("pristine-tar checkout failed, "
                              "will commit tarball due to "
                              "'--pristine-tar-commit'")
            else:
                raise
    return False


def get_upstream_tree(repo, cp, options):
    """Determine the upstream tree from the given options"""
    if options.upstream_tree.upper() == 'TAG':
        if cp['Upstream-Version'] is None:
            raise GitRepositoryError("Can't determine upstream version from changelog")
        upstream_tree = repo.version_to_tag(options.upstream_tag,
                                            cp['Upstream-Version'])
    elif options.upstream_tree.upper() == 'BRANCH':
        if not repo.has_branch(options.upstream_branch):
            raise GbpError("%s is not a valid branch" % options.upstream_branch)
        upstream_tree = options.upstream_branch
    else:
        upstream_tree = options.upstream_tree
    if not repo.has_treeish(upstream_tree):
        raise GbpError("%s is not a valid treeish" % upstream_tree)
    return upstream_tree


def git_archive_build_orig(repo, cp, output_dir, options):
    """
    Build orig tarball(s) using git-archive

    @param cp: the changelog of the package we're acting on
    @type cp: L{ChangeLog}
    @param output_dir: where to put the tarball
    @type output_dir: C{Str}
    @param options: the parsed options
    @type options: C{dict} of options
    @return: the tree we built the tarball from
    @rtype: C{str}
    """
    upstream_tree = get_upstream_tree(repo, cp, options)
    gbp.log.info("Creating %s from '%s'" % (du.orig_file(cp,
                                                         options.comp_type),
                                            upstream_tree))
    gbp.log.debug("Building upstream tarball with compression '%s -%s'" %
                  (options.comp_type, options.comp_level))
    main_tree = repo.tree_drop_dirs(upstream_tree, options.components)
    if not git_archive(repo, cp, output_dir, main_tree,
                       options.comp_type,
                       options.comp_level,
                       options.with_submodules):
        raise GbpError("Cannot create upstream tarball at '%s'" % output_dir)
    for component in options.components:
        subtree = repo.tree_get_dir(upstream_tree, component)
        if not subtree:
            raise GbpError("No tree for '%s' found in '%s' to create additional tarball from"
                           % (component, upstream_tree))
        gbp.log.info("Creating additional tarball '%s' from '%s'"
                     % (du.orig_file(cp, options.comp_type, component=component),
                        subtree))
        if not git_archive(repo, cp, output_dir, subtree,
                           options.comp_type,
                           options.comp_level,
                           options.with_submodules,
                           component=component):
            raise GbpError("Cannot create additional tarball %s at '%s'"
                           % (component, output_dir))
    return upstream_tree


def guess_comp_type(repo, comp_type, cp, tarball_dir):
    """Guess compression type"""

    srcpkg = cp['Source']
    upstream_version = cp['Upstream-Version']

    if comp_type != 'auto':
        comp_type = compressor_aliases.get(comp_type, comp_type)
        if comp_type not in compressor_opts:
            gbp.log.warn("Unknown compression type - guessing.")
            comp_type = 'auto'

    if comp_type == 'auto':
        if not repo.has_pristine_tar_branch():
            if not tarball_dir:
                tarball_dir = '..'
            detected = None
            for comp in compressor_opts.keys():
                if du.DebianPkgPolicy.has_orig(du.orig_file(cp, comp), tarball_dir):
                    if detected is not None:
                        raise GbpError("Multiple orig tarballs found.")
                    detected = comp
            if detected is not None:
                comp_type = detected
            else:
                comp_type = 'gzip'
        else:
            regex = 'pristine-tar .* %s_%s\.orig.tar\.' % (srcpkg, upstream_version)
            commits = repo.grep_log(regex, repo.pristine_tar_branch)
            if commits:
                commit = commits[-1]
                gbp.log.debug("Found pristine-tar commit at '%s'" % commit)
            else:
                commit = repo.pristine_tar_branch
            tarball = repo.get_commit_info(commit)['subject']
            (base_name, archive_fmt, comp_type) = parse_archive_filename(tarball)
            gbp.log.debug("Determined compression type '%s'" % comp_type)
            if not comp_type:
                comp_type = 'gzip'
                gbp.log.warn("Unknown compression type of %s, assuming %s" % (tarball, comp_type))
    return comp_type


def check_tag(options, repo, source):
    """Perform specified consistency checks on git history"""
    tag = repo.version_to_tag(options.debian_tag, source.changelog.version)
    if (options.tag or options.tag_only) and not options.retag:
        if repo.has_tag(tag):
            raise GbpError("Tag '%s' already exists" % tag)


def get_pbuilder_dist(options, repo, native=False):
    """
    Determin the dist to build for with pbuilder/cowbuilder
    """
    if options.pbuilder_dist == 'DEP14':
        branch = repo.branch
        if not branch:
            raise GbpError("Failed to setup DIST for %s. "
                           "Can't determine current branch." % options.builder)
        else:
            parts = branch.rsplit('/')
            if len(parts) == 2:
                vendor = du.get_vendor().lower()
                suite = parts[1]
                if vendor == parts[0]:
                    dist = '' if suite in ['sid', 'master'] else suite
                else:
                    dist = '%s_%s' % (parts[0], suite)
            elif len(parts) == 1 and native and branch in ['master', 'sid']:
                dist = ''
            else:
                raise GbpError("DEP14 DIST: Current branch '%s' does not match vendor/suite" % branch)
    else:
        dist = options.pbuilder_dist
    return dist


def setup_pbuilder(options, repo, native):
    """
    Setup environment variables for git-pbuilder

    We return two dictionaries (pbd_env, hook_env) that can be passed
    as environment when running commands

    *pbd_env* is used for the actual build command while *hook_env* is
    passed to all hooks. They both contain the same information but
    *pbd_env* contains the depreated variable names not starting with
    *GBP_*.
    """
    pbd_env = {}

    if options.use_pbuilder or options.use_qemubuilder:
        options.builder = 'git-pbuilder'
        pr_builder = os.getenv("BUILDER") or '(cowbuilder)'
        options.cleaner = '/bin/true'

        dist = get_pbuilder_dist(options, repo, native)
        pbd_env['GBP_PBUILDER_DIST'] = pbd_env['DIST'] = pr_dist = dist
        if options.pbuilder_arch:
            arch = options.pbuilder_arch
            pbd_env['GBP_PBUILDER_ARCH'] = pbd_env['ARCH'] = arch
            pr_arch = ":%s" % arch
        else:
            pr_arch = ""
        if options.use_qemubuilder:
            pbd_env['GBP_PBUILDER_BUILDER'] = pbd_env['BUILDER'] = "qemubuilder"
            pr_builder = pbd_env["GBP_PBUILDER_BUILDER"]
        if not options.pbuilder_autoconf:
            pbd_env['GBP_PBUILDER_AUTOCONF'] = pbd_env['GIT_PBUILDER_AUTOCONF'] = "no"
        if options.pbuilder_options:
            pbd_env['GBP_PBUILDER_OPTIONS'] = pbd_env['GIT_PBUILDER_OPTIONS'] = options.pbuilder_options
        gbp.log.info("Building with %s for %s%s" % (pr_builder, pr_dist, pr_arch))

    hook_env = dict([(k, pbd_env[k]) for k in pbd_env if k.startswith("GBP_")])
    return pbd_env, hook_env


def disable_hooks(options):
    """Disable all hooks (except for builder)"""
    for hook in ['cleaner', 'postexport', 'prebuild', 'postbuild', 'posttag']:
        if getattr(options, hook):
            gbp.log.info("Disabling '%s' hook" % hook)
            setattr(options, hook, '')


def changes_file_suffix(dpkg_args):
    """
    >>> changes_file_suffix(['-A'])
    'all'
    >>> changes_file_suffix(['-S'])
    'source'
    >>> changes_file_suffix([]) == du.get_arch()
    True
    """
    if '-S' in dpkg_args:
        return 'source'
    elif '-A' in dpkg_args:
        return 'all'
    else:
        return os.getenv('ARCH', None) or du.get_arch()


def build_parser(name, prefix=None):
    try:
        parser = GbpOptionParserDebian(command=os.path.basename(name), prefix=prefix)
    except GbpError as err:
        gbp.log.err(err)
        return None

    tag_group = GbpOptionGroup(parser,
                               "tag options",
                               "options related to git tag creation")
    orig_group = GbpOptionGroup(parser,
                                "orig tarball options",
                                "options related to the creation of the orig tarball")
    branch_group = GbpOptionGroup(parser,
                                  "branch options",
                                  "branch layout options")
    cmd_group = GbpOptionGroup(parser,
                               "external command options",
                               "how and when to invoke external commands and hooks")
    export_group = GbpOptionGroup(parser,
                                  "export build-tree options",
                                  "alternative build tree related options")
    for group in [tag_group, orig_group, branch_group, cmd_group, export_group]:
        parser.add_option_group(group)

    parser.add_boolean_config_file_option(option_name="ignore-new", dest="ignore_new")
    parser.add_option("--git-verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    parser.add_config_file_option(option_name="notify", dest="notify", type='tristate')
    tag_group.add_option("--git-tag", action="store_true", dest="tag", default=False,
                         help="create a tag after a successful build")
    tag_group.add_option("--git-tag-only", action="store_true", dest="tag_only", default=False,
                         help="don't build, only tag and run the posttag hook")
    tag_group.add_option("--git-retag", action="store_true", dest="retag", default=False,
                         help="don't fail if the tag already exists")
    tag_group.add_boolean_config_file_option(option_name="sign-tags", dest="sign_tags")
    tag_group.add_config_file_option(option_name="keyid", dest="keyid")
    tag_group.add_config_file_option(option_name="debian-tag", dest="debian_tag")
    tag_group.add_config_file_option(option_name="debian-tag-msg", dest="debian_tag_msg")
    tag_group.add_config_file_option(option_name="upstream-tag", dest="upstream_tag")
    orig_group.add_config_file_option(option_name="upstream-tree", dest="upstream_tree")
    orig_group.add_boolean_config_file_option(option_name="pristine-tar", dest="pristine_tar")
    orig_group.add_boolean_config_file_option(option_name="pristine-tar-commit",
                                              dest="pristine_tar_commit")
    orig_group.add_config_file_option(option_name="force-create", dest="force_create",
                                      help="force creation of orig tarball", action="store_true")
    orig_group.add_config_file_option(option_name="no-create-orig", dest="no_create_orig",
                                      help="don't create orig tarball", action="store_true")
    orig_group.add_config_file_option(option_name="tarball-dir", dest="tarball_dir", type="path",
                                      help="location to look for external tarballs")
    orig_group.add_config_file_option(option_name="compression", dest="comp_type",
                                      help="Compression type, default is '%(compression)s'")
    orig_group.add_config_file_option(option_name="compression-level", dest="comp_level",
                                      help="Compression level, default is '%(compression-level)s'")
    orig_group.add_config_file_option("component", action="append", metavar='COMPONENT',
                                      dest="components")
    branch_group.add_config_file_option(option_name="upstream-branch", dest="upstream_branch")
    branch_group.add_config_file_option(option_name="debian-branch", dest="debian_branch")
    branch_group.add_boolean_config_file_option(option_name="ignore-branch", dest="ignore_branch")
    branch_group.add_boolean_config_file_option(option_name="submodules", dest="with_submodules")
    cmd_group.add_config_file_option(option_name="builder", dest="builder",
                                     help="command to build the Debian package, "
                                          "default is '%(builder)s'")
    cmd_group.add_config_file_option(option_name="cleaner", dest="cleaner",
                                     help="command to clean the working copy, "
                                          "default is '%(cleaner)s'")
    cmd_group.add_config_file_option(option_name="prebuild", dest="prebuild",
                                     help="hook to run before a build, "
                                          "default is '%(prebuild)s'")
    cmd_group.add_config_file_option(option_name="postexport", dest="postexport",
                                     help="hook to run after exporting the source tree, "
                                          "default is '%(postexport)s'")
    cmd_group.add_config_file_option(option_name="postbuild", dest="postbuild",
                                     help="hook run after a successful build, "
                                          "default is '%(postbuild)s'")
    cmd_group.add_config_file_option(option_name="posttag", dest="posttag",
                                     help="hook run after a successful tag operation, "
                                          "default is '%(posttag)s'")
    cmd_group.add_boolean_config_file_option(option_name="pbuilder", dest="use_pbuilder")
    cmd_group.add_boolean_config_file_option(option_name="qemubuilder", dest="use_qemubuilder")
    cmd_group.add_config_file_option(option_name="dist", dest="pbuilder_dist")
    cmd_group.add_config_file_option(option_name="arch", dest="pbuilder_arch")
    cmd_group.add_boolean_config_file_option(option_name="pbuilder-autoconf",
                                             dest="pbuilder_autoconf")
    cmd_group.add_config_file_option(option_name="pbuilder-options", dest="pbuilder_options")
    cmd_group.add_boolean_config_file_option(option_name="hooks", dest="hooks")
    export_group.add_config_file_option(option_name="export-dir", dest="export_dir", type="path",
                                        help="before building the package export the source into EXPORT_DIR, "
                                             "default is '%(export-dir)s'")
    export_group.add_config_file_option("export", dest="export",
                                        help="export treeish object TREEISH, "
                                             "default is '%(export)s'", metavar="TREEISH")
    export_group.add_boolean_config_file_option(option_name="purge", dest="purge")
    export_group.add_option("--git-dont-purge", action="store_true", dest="dont_purge", default=False,
                            help="deprecated, use --git-no-purge instead")
    export_group.add_boolean_config_file_option(option_name="overlay", dest="overlay")
    return parser


def parse_args(argv, prefix):
    args = [arg for arg in argv[1:] if arg.find('--%s' % prefix) == 0]
    dpkg_args = [arg for arg in argv[1:] if arg.find('--%s' % prefix) == -1]

    # We handle these although they don't have a --git- prefix
    for arg in ["--help", "-h", "--version"]:
        if arg in dpkg_args:
            args.append(arg)

    parser = build_parser(argv[0], prefix=prefix)
    if not parser:
        return None, None, None
    options, args = parser.parse_args(args)

    gbp.log.setup(options.color, options.verbose, options.color_scheme)
    if not options.hooks:
        disable_hooks(options)
    if options.retag:
        if not options.tag and not options.tag_only:
            gbp.log.err("'--%sretag' needs either '--%stag' or '--%stag-only'"
                        % (prefix, prefix, prefix))
            return None, None, None

    if options.overlay and not options.export_dir:
        gbp.log.err("Overlay must be used with --git-export-dir")
        return None, None, None

    # --git-dont-purge is deprecated:
    if options.dont_purge:
        gbp.log.warn("--git-dont-purge is depreceted, use --git-no-purge instead")
        options.purge = False

    if options.components and options.pristine_tar_commit:
        gbp.log.warn("Components specified, pristine-tar-commit not yet supported - disabling it.")
        options.pristine_tar_commit = False

    return options, args, dpkg_args


def main(argv):
    retval = 0
    prefix = "git-"
    source = None
    branch = None
    hook_env = {}

    options, gbp_args, dpkg_args = parse_args(argv, prefix)

    if not options:
        return ExitCodes.parse_error

    try:
        repo = DebianGitRepository(os.path.curdir)
    except GitRepositoryError:
        gbp.log.err("%s is not a git repository" % (os.path.abspath('.')))
        return 1

    try:
        Command(options.cleaner, shell=True)()
        if not options.ignore_new:
            (ret, out) = repo.is_clean()
            if not ret:
                gbp.log.err("You have uncommitted changes in your source tree:")
                gbp.log.err(out)
                raise GbpError("Use --git-ignore-new to ignore.")

        try:
            branch = repo.get_branch()
        except GitRepositoryError:
            # Not being on any branch is o.k. with --git-ignore-branch
            if not options.ignore_branch:
                raise

        if not options.ignore_new and not options.ignore_branch:
            if branch != options.debian_branch:
                gbp.log.err("You are not on branch '%s' but on '%s'" % (options.debian_branch, branch))
                raise GbpError("Use --git-ignore-branch to ignore or --git-debian-branch to set the branch name.")

        head = repo.head
        tree = write_tree(repo, options)
        source = source_vfs(repo, options, tree)

        check_tag(options, repo, source)

        if not options.tag_only:
            output_dir = prepare_output_dir(options.export_dir)
            tarball_dir = options.tarball_dir or output_dir

            # Get/build the upstream tarball if necessary. We delay this in
            # case of a postexport hook so the hook gets a chance to modify the
            # sources and create different tarballs (#640382)
            # We don't delay it in general since we want to fail early if the
            # tarball is missing.
            if not source.is_native():
                if options.postexport:
                    gbp.log.info("Postexport hook set, delaying tarball creation")
                else:
                    prepare_upstream_tarball(repo, source.changelog, options, tarball_dir,
                                             output_dir)

            build_env, hook_env = setup_pbuilder(options, repo, source.is_native())

            # Export to another build dir if requested:
            if options.export_dir:
                tmp_dir = os.path.join(output_dir, "%s-tmp" % source.sourcepkg)
                export_source(repo, tree, source, options, tmp_dir, output_dir)

                # Run postexport hook
                if options.postexport:
                    Hook('Postexport', options.postexport,
                         extra_env=Hook.md(hook_env,
                                           {'GBP_GIT_DIR': repo.git_dir,
                                            'GBP_TMP_DIR': tmp_dir})
                         )(dir=tmp_dir)

                major = (source.changelog.debian_version if source.is_native()
                         else source.changelog.upstream_version)
                export_dir = os.path.join(output_dir, "%s-%s" % (source.sourcepkg, major))
                gbp.log.info("Moving '%s' to '%s'" % (tmp_dir, export_dir))
                move_old_export(export_dir)
                os.rename(tmp_dir, export_dir)

                # Delayed tarball creation in case a postexport hook is used:
                if not source.is_native() and options.postexport:
                    prepare_upstream_tarball(repo, source.changelog, options, tarball_dir,
                                             output_dir)
                build_dir = export_dir
            else:
                build_dir = repo.path

            if options.prebuild:
                Hook('Prebuild', options.prebuild,
                     extra_env=Hook.md(hook_env,
                                       {'GBP_GIT_DIR': repo.git_dir,
                                        'GBP_BUILD_DIR': build_dir})
                     )(dir=build_dir)

            # Finally build the package:
            RunAtCommand(options.builder, dpkg_args, shell=True,
                         extra_env=Hook.md(build_env,
                                           {'GBP_BUILD_DIR': build_dir})
                         )(dir=build_dir)
            if options.postbuild:
                changes = os.path.abspath("%s/../%s_%s_%s.changes" %
                                          (build_dir,
                                           source.sourcepkg,
                                           source.changelog.noepoch,
                                           changes_file_suffix(dpkg_args)))
                gbp.log.debug("Looking for changes file %s" % changes)
                Hook('Postbuild', options.postbuild,
                     extra_env=Hook.md(hook_env,
                                       {'GBP_CHANGES_FILE': changes,
                                        'GBP_BUILD_DIR': build_dir})
                     )()
        if options.tag or options.tag_only:
            tag = repo.version_to_tag(options.debian_tag, source.changelog.version)
            gbp.log.info("Tagging %s as %s" % (source.changelog.version, tag))
            if options.retag and repo.has_tag(tag):
                repo.delete_tag(tag)
            tag_msg = format_str(options.debian_tag_msg,
                                 dict(pkg=source.sourcepkg,
                                      version=source.changelog.version))
            repo.create_tag(name=tag,
                            msg=tag_msg,
                            sign=options.sign_tags,
                            commit=head,
                            keyid=options.keyid)
            if options.posttag:
                sha = repo.rev_parse("%s^{}" % tag)
                Hook('Posttag', options.posttag,
                     extra_env=Hook.md(hook_env,
                                       {'GBP_TAG': tag,
                                        'GBP_BRANCH': branch or '(no branch)',
                                        'GBP_SHA1': sha})
                     )()
    except KeyboardInterrupt:
        retval = 1
        gbp.log.err("Interrupted. Aborting.")
    except CommandExecFailed:
        retval = 1
    except (GbpError, GitRepositoryError) as err:
        if str(err):
            gbp.log.err(err)
        retval = 1
    except DebianSourceError as err:
        gbp.log.err(err)
        source = None
        retval = 1
    finally:
        drop_index()

    if not options.tag_only:
        if options.export_dir and options.purge and not retval:
            RemoveTree(export_dir)()

        if source:
            summary, msg = gbp.notifications.build_msg(source.changelog,
                                                       not retval)
            if not gbp.notifications.notify(summary, msg, options.notify):
                gbp.log.err("Failed to send notification")
                retval = 1

    return retval


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
