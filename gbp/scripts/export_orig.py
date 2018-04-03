# vim: set fileencoding=utf-8 :
#
# (C) 2017 Guido Günther <agx@sigxcpu.org>
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
"""Create orig tarballs from git"""

import os
import sys
import gbp.deb as du
from gbp.command_wrappers import CommandExecFailed
from gbp.config import (GbpOptionParserDebian, GbpOptionGroup)
from gbp.deb.git import (GitRepositoryError, DebianGitRepository)
from gbp.deb.source import DebianSource, DebianSourceError
from gbp.errors import GbpError
import gbp.log
import gbp.notifications
from gbp.scripts.common import ExitCodes
from gbp.pkg import Compressor, Archive


def prepare_upstream_tarballs(repo, source, options, tarball_dir, output_dir):
    """
    Make sure we have the needed upstream tarballs. The default order is:
    - look in tarball_dir and if found symlink to it
    - create tarball using pristine-tar
    - create tarball using git-archive

    Afterwards
    - create pristine-tar commmits if pristine-tar-commit is in use
    - verify tarball checksums if pristine-tar is in use
    """
    if hasattr(options, 'no_create_orig') and options.no_create_orig:
        return

    if not source.is_native() and not source.upstream_version:
        raise GbpError("Non-native package '%s' "
                       "has invalid version '%s'" % (source.name, source.version))

    options.comp_type = guess_comp_type(options.comp_type,
                                        source,
                                        repo,
                                        options.tarball_dir)
    orig_files = source.upstream_tarball_names(options.comp_type, options.components)

    # look in tarball_dir first, if found force a symlink to it
    if options.tarball_dir:
        gbp.log.debug("Looking for orig tarballs '%s' at '%s'" % (", ".join(orig_files), tarball_dir))
        missing = du.DebianPkgPolicy.symlink_origs(orig_files, tarball_dir, output_dir, force=True)
        if missing:
            msg = "Tarballs '%s' not found at '%s'" % (", ".join(missing), tarball_dir)
        else:
            msg = "All Orig tarballs '%s' found at '%s'" % (", ".join(orig_files), tarball_dir)
        gbp.log.info(msg)

    # Create tarball if missing or forced
    if not du.DebianPkgPolicy.has_origs(orig_files, output_dir) or options.force_create:
        if not pristine_tar_build_origs(repo, source, output_dir, options):
            git_archive_build_origs(repo, source, output_dir, options)
    maybe_pristine_tar_commit(repo, source, options, output_dir, orig_files)
    pristine_tar_verify_origs(repo, source, options, output_dir, orig_files)


def pristine_tar_prepare_orig_tree(repo, source, options):
    """
    Make sure the upstream tree exists

    In case of component tarballs we need to recreate a tree for the
    main tarball without the component subdirs.
    """
    if options.components:
        try:
            upstream_tag = repo.version_to_tag(options.upstream_tag,
                                               source.upstream_version)
            tree_name = "%s^{tree}" % upstream_tag
            repo.tree_drop_dirs(tree_name, options.components)
        except GitRepositoryError:
            raise GbpError("Couldn't find upstream tree '%s' to create "
                           "orig tarball via pristine-tar" % tree_name)


def pristine_tar_build_origs(repo, source, output_dir, options):
    """
    Build orig tarball using pristine-tar

    @returns: C{True} if tarball was build, C{False} otherwise
    """
    if not options.pristine_tar:
        return False

    if not repo.has_branch(repo.pristine_tar_branch):
        gbp.log.warn('Pristine-tar branch "%s" not found' %
                     repo.pristine_tar.branch)

    comp = Compressor(options.comp_type)
    pristine_tar_prepare_orig_tree(repo, source, options)
    try:
        gbp.log.info("Creating %s" %
                     os.path.abspath(os.path.join(output_dir,
                                                  source.upstream_tarball_name(comp.type))))
        repo.create_upstream_tarball_via_pristine_tar(source,
                                                      output_dir,
                                                      comp)
        for component in options.components:
            gbp.log.info("Creating %s" %
                         os.path.abspath(os.path.join(output_dir,
                                                      source.upstream_tarball_name(comp.type, component))))
            repo.create_upstream_tarball_via_pristine_tar(source,
                                                          output_dir,
                                                          comp,
                                                          component=component)
        return True
    except GitRepositoryError:
        if hasattr(options, 'pristine_tar_commit') and options.pristine_tar_commit:
            gbp.log.debug("pristine-tar checkout failed, will commit tarball "
                          "due to '--pristine-tar-commit'")
        else:
            raise
    return False


def pristine_tar_verify_origs(repo, source, options, output_dir, orig_files):
    """
    Verify orig tarballs using prstine tar

    @returns: C{True} if tarball was build, C{False} otherwise
    """
    if not options.pristine_tar:
        return True

    if not repo.pristine_tar.has_feature_verify():
        gbp.log.warn("pristine-tar does not support verify. "
                     "Skipping verification.")
        return True

    pristine_tar_prepare_orig_tree(repo, source, options)
    for f in orig_files:
        repo.pristine_tar.verify(os.path.join(output_dir, f))
    return True


def maybe_pristine_tar_commit(repo, source, options, output_dir, orig_files):
    if not (hasattr(options, 'pristine_tar_commit') and options.pristine_tar_commit):
        return

    if repo.pristine_tar.has_commit(source.name,
                                    source.upstream_version,
                                    options.comp_type):
        gbp.log.debug("%s already on pristine tar branch" % orig_files[0])
    else:
        upstream_tree = git_archive_get_upstream_tree(repo, source, options)
        archive = os.path.join(output_dir, orig_files[0])
        gbp.log.debug("Adding %s to pristine-tar branch" % archive)
        repo.pristine_tar.commit(archive, upstream_tree)


def git_archive_get_upstream_tree(repo, source, options):
    """
    Determine the upstream tree from the given options

    for a git archive export
    """
    if options.upstream_tree.upper() == 'TAG':
        if source.upstream_version is None:
            raise GitRepositoryError("Can't determine upstream version from changelog")
        upstream_tree = repo.version_to_tag(options.upstream_tag,
                                            source.upstream_version)
    elif options.upstream_tree.upper() == 'BRANCH':
        if not repo.has_branch(options.upstream_branch):
            raise GbpError("%s is not a valid branch" % options.upstream_branch)
        upstream_tree = options.upstream_branch
    elif options.upstream_tree.upper() == 'SLOPPY':
        tree_name = "%s^{tree}" % options.debian_branch
        upstream_tree = repo.tree_drop_dirs(tree_name, ["debian"])
    else:
        upstream_tree = options.upstream_tree
    if not repo.has_treeish(upstream_tree):
        raise GbpError("%s is not a valid treeish" % upstream_tree)
    return upstream_tree


def git_archive_build_origs(repo, source, output_dir, options):
    """
    Build orig tarball(s) using git-archive

    @param source: the source of the package we're acting on
    @type source: L{DebianSource}
    @param output_dir: where to put the tarball
    @type output_dir: C{Str}
    @param options: the parsed options
    @type options: C{dict} of options
    """
    comp = Compressor(options.comp_type, options.comp_level)
    upstream_tree = git_archive_get_upstream_tree(repo, source, options)
    gbp.log.info("Creating %s from '%s'" % (source.upstream_tarball_name(comp.type),
                                            upstream_tree))
    gbp.log.debug("Building upstream tarball with compression %s" % comp)
    tree = repo.tree_drop_dirs(upstream_tree, options.components) if options.components else upstream_tree
    repo.create_upstream_tarball_via_git_archive(source, output_dir, tree, comp, options.with_submodules)
    for component in options.components:
        subtree = repo.tree_get_dir(upstream_tree, component)
        if not subtree:
            raise GbpError("No tree for '%s' found in '%s' to create additional tarball from"
                           % (component, upstream_tree))
        gbp.log.info("Creating additional tarball '%s' from '%s'"
                     % (source.upstream_tarball_name(options.comp_type, component=component),
                        subtree))
        repo.create_upstream_tarball_via_git_archive(source, output_dir, subtree, comp,
                                                     options.with_submodules, component=component)


def guess_comp_type(comp_type, source, repo, tarball_dir):
    """Guess compression type to use for the to be built upstream tarball

    We prefer pristine-tar over everything else since this is what's carried around with
    the repo and might be more reliable than what a user has in tarball_dir.
    """
    if comp_type != 'auto':
        comp_type = Compressor.Aliases.get(comp_type, comp_type)
        if comp_type not in Compressor.Opts:
            gbp.log.warn("Unknown compression type - guessing.")
            comp_type = 'auto'

    if comp_type == 'auto':
        if repo and repo.has_pristine_tar_branch():
            regex = 'pristine-tar .* %s_%s\.orig.tar\.' % (source.name, source.upstream_version)
            commits = repo.grep_log(regex, repo.pristine_tar_branch)
            if commits:
                commit = commits[-1]
                gbp.log.debug("Found pristine-tar commit at '%s'" % commit)
            else:
                commit = repo.pristine_tar_branch
            tarball = repo.get_commit_info(commit)['subject']
            (base_name, archive_fmt, comp_type) = Archive.parse_filename(tarball)
            gbp.log.debug("Determined compression type '%s'" % comp_type)
            if not comp_type:
                comp_type = 'gzip'
                gbp.log.warn("Unknown compression type of %s, assuming %s" % (tarball, comp_type))
        else:
            if not tarball_dir:
                tarball_dir = '..'
            detected = None
            for comp in Compressor.Opts.keys():
                if du.DebianPkgPolicy.has_orig(source.upstream_tarball_name(comp), tarball_dir):
                    if detected is not None:
                        raise GbpError("Multiple orig tarballs found.")
                    detected = comp
            comp_type = 'gzip' if detected is None else detected
    return comp_type


def build_parser(name):
    try:
        parser = GbpOptionParserDebian(command=os.path.basename(name), prefix='')
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
    for group in [tag_group, orig_group, branch_group]:
        parser.add_option_group(group)

    parser.add_option("--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    tag_group.add_config_file_option(option_name="upstream-tag", dest="upstream_tag")
    orig_group.add_config_file_option(option_name="upstream-tree", dest="upstream_tree")
    orig_group.add_boolean_config_file_option(option_name="pristine-tar", dest="pristine_tar")
    orig_group.add_config_file_option(option_name="force-create", dest="force_create",
                                      help="force creation of orig tarball", action="store_true")
    orig_group.add_config_file_option(option_name="tarball-dir", dest="tarball_dir", type="path",
                                      help="location to look for external tarballs")
    orig_group.add_config_file_option(option_name="compression", dest="comp_type",
                                      help="Compression type, default is '%(compression)s'")
    orig_group.add_config_file_option(option_name="compression-level", dest="comp_level",
                                      help="Compression level, default is '%(compression-level)s'")
    orig_group.add_config_file_option("component", action="append", metavar='COMPONENT',
                                      dest="components")
    branch_group.add_config_file_option(option_name="upstream-branch", dest="upstream_branch")
    branch_group.add_boolean_config_file_option(option_name="submodules", dest="with_submodules")
    return parser


def parse_args(argv, prefix):
    parser = build_parser(argv[0])
    if not parser:
        return None, None
    options, args = parser.parse_args(argv[1:])

    gbp.log.setup(options.color, options.verbose, options.color_scheme)
    return options, args


def main(argv):
    retval = 0
    source = None

    options, args = parse_args(argv, '')

    if args or not options:
        return ExitCodes.parse_error

    try:
        repo = DebianGitRepository(os.path.curdir, toplevel=False)
    except GitRepositoryError:
        gbp.log.err("%s is not inside a git repository" % (os.path.abspath('.')))
        return 1

    try:
        try:
            source = DebianSource(repo.path)
            source.is_native()
        except Exception as e:
            raise GbpError("Can't determine package type: %s" % e)

        output_dir = options.tarball_dir or os.path.join(repo.path, '..')

        if source.is_native():
            gbp.log.info("Nothing to be done for native package")
            return 0

        prepare_upstream_tarballs(repo, source, options, output_dir,
                                  output_dir)
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

    return retval


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
