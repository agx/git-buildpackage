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
import gbp.deb as du
from gbp.command_wrappers import CommandExecFailed
from gbp.deb.git import GitRepositoryError
from gbp.errors import GbpError
import gbp.log
import gbp.notifications
from gbp.scripts.common.buildpackage import (git_archive_submodules,
                                             git_archive_single)
from gbp.pkg import compressor_opts, compressor_aliases, parse_archive_filename


# upstream tarball preparation
def git_archive(repo, source, output_dir, treeish, comp_type, comp_level, with_submodules, component=None):
    "create a compressed orig tarball in output_dir using git_archive"
    try:
        comp_opts = compressor_opts[comp_type][0]
    except KeyError:
        raise GbpError("Unsupported compression type '%s'" % comp_type)

    output = os.path.join(output_dir,
                          source.upstream_tarball_name(comp_type, component=component))
    prefix = "%s-%s" % (source.name, source.upstream_version)

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


def prepare_upstream_tarballs(repo, source, options, tarball_dir, output_dir):
    """
    Make sure we have the needed upstream tarballs. This involves
    looking in tarball_dir and symlinking them or building them from either
    pristine-tar or plain git.
    """
    if not source.is_native() and not source.upstream_version:
        raise GbpError("Non-native package '%s' "
                       "has invalid version '%s'" % (source.name, source.version))

    options.comp_type = guess_comp_type(repo,
                                        options.comp_type,
                                        source,
                                        options.tarball_dir)

    orig_files = [source.upstream_tarball_name(options.comp_type)]
    if options.components:
        orig_files += [source.upstream_tarball_name(options.comp_type, c) for c in options.components]

    # look in tarball_dir first, if found force a symlink to it
    if options.tarball_dir:
        gbp.log.debug("Looking for orig tarballs '%s' at '%s'" % (", ".join(orig_files), tarball_dir))
        missing = du.DebianPkgPolicy.symlink_origs(orig_files, tarball_dir, output_dir, force=True)
        if missing:
            msg = "Tarballs '%s' not found at '%s'" % (", ".join(missing), tarball_dir)
        else:
            msg = "All Orig tarballs '%s' found at '%s'" % (", ".join(orig_files), tarball_dir)
        gbp.log.info(msg)
    # FIXME: trouble with "gbp buildpackage"
    # if options.no_create_orig:
    #     return
    # Create tarball if missing or forced
    if not du.DebianPkgPolicy.has_origs(orig_files, output_dir) or options.force_create:
        if not pristine_tar_build_orig(repo, source, output_dir, options):
            git_archive_build_orig(repo, source, output_dir, options)
    pristine_tar_verify_orig(repo, source, options, output_dir, orig_files)


def pristine_tar_prepare_orig_tree(repo, source, options):
    """Make sure the upstream tree exists
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


def pristine_tar_build_orig(repo, source, output_dir, options):
    """
    Build orig tarball using pristine-tar

    @returns: C{True} if tarball was build, C{False} otherwise
    """
    if options.pristine_tar:
        if not repo.has_branch(repo.pristine_tar_branch):
            gbp.log.warn('Pristine-tar branch "%s" not found' %
                         repo.pristine_tar.branch)

        pristine_tar_prepare_orig_tree(repo, source, options)
        try:
            repo.pristine_tar.checkout(source.name,
                                       source.upstream_version,
                                       options.comp_type,
                                       output_dir)
            for component in options.components:
                repo.pristine_tar.checkout(source.name,
                                           source.upstream_version,
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


def pristine_tar_verify_orig(repo, source, options, output_dir, orig_files):
    """
    Verify orig tarballs using prstine tar

    @returns: C{True} if tarball was build, C{False} otherwise
    """
    if not options.pristine_tar:
        return True

    pristine_tar_prepare_orig_tree(repo, source, options)
    for f in orig_files:
        repo.pristine_tar.verify(os.path.join(output_dir, f))
    return True


def get_upstream_tree(repo, source, options):
    """Determine the upstream tree from the given options"""
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


def git_archive_build_orig(repo, source, output_dir, options):
    """
    Build orig tarball(s) using git-archive

    @param source: the changelog of the package we're acting on
    @type source: L{DebianSource}
    @param output_dir: where to put the tarball
    @type output_dir: C{Str}
    @param options: the parsed options
    @type options: C{dict} of options
    @return: the tree we built the tarball from
    @rtype: C{str}
    """
    upstream_tree = get_upstream_tree(repo, source, options)
    gbp.log.info("Creating %s from '%s'" % (source.upstream_tarball_name(options.comp_type),
                                            upstream_tree))
    comp_level = int(options.comp_level) if options.comp_level != '' else None
    gbp.log.debug("Building upstream tarball with compression '%s'%s" %
                  (options.comp_type,
                   "' -%s'" % comp_level if comp_level is not None else ''))
    main_tree = repo.tree_drop_dirs(upstream_tree, options.components) if options.components else upstream_tree
    if not git_archive(repo, source, output_dir, main_tree,
                       options.comp_type,
                       comp_level,
                       options.with_submodules):
        raise GbpError("Cannot create upstream tarball at '%s'" % output_dir)
    for component in options.components:
        subtree = repo.tree_get_dir(upstream_tree, component)
        if not subtree:
            raise GbpError("No tree for '%s' found in '%s' to create additional tarball from"
                           % (component, upstream_tree))
        gbp.log.info("Creating additional tarball '%s' from '%s'"
                     % (source.upstream_tarball_name(options.comp_type, component=component),
                        subtree))
        if not git_archive(repo, source, output_dir, subtree,
                           options.comp_type,
                           comp_level,
                           options.with_submodules,
                           component=component):
            raise GbpError("Cannot create additional tarball %s at '%s'"
                           % (component, output_dir))
    return upstream_tree


def guess_comp_type(repo, comp_type, source, tarball_dir):
    """Guess compression type to use for to be built upstream tarball"""
    if comp_type != 'auto':
        comp_type = compressor_aliases.get(comp_type, comp_type)
        if comp_type not in compressor_opts:
            gbp.log.warn("Unknown compression type - guessing.")
            comp_type = 'auto'

    if comp_type == 'auto':
        if repo.has_pristine_tar_branch():
            regex = 'pristine-tar .* %s_%s\.orig.tar\.' % (source.name, source.upstream_version)
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
        else:
            if not tarball_dir:
                tarball_dir = '..'
            detected = None
            for comp in compressor_opts.keys():
                if du.DebianPkgPolicy.has_orig(source.upstream_tarball_name(comp), tarball_dir):
                    if detected is not None:
                        raise GbpError("Multiple orig tarballs found.")
                    detected = comp
            comp_type = 'gzip' if detected is None else detected
    return comp_type
