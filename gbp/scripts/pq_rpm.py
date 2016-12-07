# vim: set fileencoding=utf-8 :
#
# (C) 2011,2016 Guido Günther <agx@sigxcpu.org>
# (C) 2012-2014 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""manage patches in a patch queue"""

import bz2
import errno
import gzip
import os
import re
import sys

import gbp.log
from gbp.tmpfile import init_tmpdir, del_tmpdir, tempfile
from gbp.config import GbpOptionParserRpm
from gbp.rpm.git import GitRepositoryError, RpmGitRepository
from gbp.git.modifier import GitModifier
from gbp.command_wrappers import GitCommand, CommandExecFailed
from gbp.errors import GbpError
from gbp.patch_series import PatchSeries, Patch
from gbp.pkg import parse_archive_filename
from gbp.rpm import (SpecFile, NoSpecError, guess_spec, guess_spec_repo,
                     spec_from_repo)
from gbp.scripts.common import ExitCodes
from gbp.scripts.common.pq import (is_pq_branch, pq_branch_name, pq_branch_base,
                                   parse_gbp_commands, format_patch, format_diff,
                                   switch_to_pq_branch, apply_single_patch,
                                   apply_and_commit_patch,
                                   drop_pq, switch_pq)

from gbp.scripts.common.buildpackage import dump_tree


def is_ancestor(repo, parent, child):
    """Check if commit is ancestor of another"""
    parent_sha1 = repo.rev_parse("%s^0" % parent)
    child_sha1 = repo.rev_parse("%s^0" % child)
    try:
        merge_base = repo.get_merge_base(parent_sha1, child_sha1)
    except GitRepositoryError:
        merge_base = None
    return merge_base == parent_sha1


def generate_patches(repo, start, end, outdir, options):
    """
    Generate patch files from git
    """
    gbp.log.info("Generating patches from git (%s..%s)" % (start, end))
    patches = []
    commands = {}
    for treeish in [start, end]:
        if not repo.has_treeish(treeish):
            raise GbpError('Invalid treeish object %s' % treeish)

    start_sha1 = repo.rev_parse("%s^0" % start)
    try:
        end_commit = end
    except GitRepositoryError:
        # In case of plain tree-ish objects, assume current branch head is the
        # last commit
        end_commit = "HEAD"
    end_commit_sha1 = repo.rev_parse("%s^0" % end_commit)

    start_sha1 = repo.rev_parse("%s^0" % start)

    if not is_ancestor(repo, start_sha1, end_commit_sha1):
        raise GbpError("Start commit '%s' not an ancestor of end commit "
                       "'%s'" % (start, end_commit))
    # Check for merge commits, squash if merges found
    merges = repo.get_commits(start, end_commit, options=['--merges'])
    if merges:
        # Shorten SHA1s
        start_sha1 = repo.rev_parse(start, short=7)
        merge_sha1 = repo.rev_parse(merges[0], short=7)
        patch_fn = format_diff(outdir, None, repo, start_sha1, merge_sha1)
        if patch_fn:
            gbp.log.info("Merge commits found! Diff between %s..%s written "
                         "into one monolithic diff" % (start_sha1, merge_sha1))
            patches.append(patch_fn)
            start = merge_sha1

    # Generate patches
    for commit in reversed(repo.get_commits(start, end_commit)):
        info = repo.get_commit_info(commit)
        (cmds, info['body']) = parse_gbp_commands(info,
                                                  'gbp-rpm',
                                                  ('ignore'),
                                                  ('if', 'ifarch'))
        if 'ignore' not in cmds:
            patch_fn = format_patch(outdir, repo, info, patches,
                                    options.patch_numbers)
            if patch_fn:
                commands[os.path.basename(patch_fn)] = cmds
        else:
            gbp.log.info('Ignoring commit %s' % info['id'])

    # Generate diff to the tree-ish object
    if end_commit != end:
        gbp.log.info("Generating diff file %s..%s" % (end_commit, end))
        patch_fn = format_diff(outdir, None, repo, end_commit, end,
                               options.patch_export_ignore_path)
        if patch_fn:
            patches.append(patch_fn)

    return [os.path.relpath(p) for p in patches], commands


def rm_patch_files(spec):
    """
    Delete the patch files listed in the spec file. Doesn't delete patches
    marked as not maintained by gbp.
    """
    # Remove all old patches from the spec dir
    for patch in spec.patchseries(unapplied=True):
        gbp.log.debug("Removing '%s'" % patch.path)
        try:
            os.unlink(patch.path)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise GbpError("Failed to remove patch: %s" % err)
            else:
                gbp.log.debug("Patch %s does not exist." % patch.path)


def update_patch_series(repo, spec, start, end, options):
    """
    Export patches to packaging directory and update spec file accordingly.
    """
    # Unlink old patch files and generate new patches
    rm_patch_files(spec)

    patches, commands = generate_patches(repo, start, end,
                                         spec.specdir, options)
    spec.update_patches(patches, commands)
    spec.write_spec_file()
    return patches


def parse_spec(options, repo, treeish=None):
    """
    Find and parse spec file.

    If treeish is given, try to find the spec file from that. Otherwise, search
    for the spec file in the working copy.
    """
    try:
        if options.spec_file:
            if not treeish:
                spec = SpecFile(options.spec_file)
            else:
                spec = spec_from_repo(repo, treeish, options.spec_file)
        else:
            preferred_name = os.path.basename(repo.path) + '.spec'
            if not treeish:
                spec = guess_spec(options.packaging_dir, True, preferred_name)
            else:
                spec = guess_spec_repo(repo, treeish, options.packaging_dir,
                                       True, preferred_name)
    except NoSpecError as err:
        raise GbpError("Can't parse spec: %s" % err)
    relpath = spec.specpath if treeish else os.path.relpath(spec.specpath,
                                                            repo.path)
    options.packaging_dir = os.path.dirname(relpath)
    gbp.log.debug("Using '%s' from '%s'" % (relpath, treeish or 'working copy'))
    return spec


def find_upstream_commit(repo, spec, upstream_tag):
    """Find commit corresponding upstream version"""
    tag_str_fields = {'upstreamversion': spec.upstreamversion,
                      'version': spec.upstreamversion}
    upstream_commit = repo.find_version(upstream_tag, tag_str_fields)
    if not upstream_commit:
        raise GbpError("Couldn't find upstream version %s" %
                       spec.upstreamversion)
    return upstream_commit


def export_patches(repo, options):
    """Export patches from the pq branch into a packaging branch"""
    current = repo.get_branch()
    if is_pq_branch(current):
        base = pq_branch_base(current)
        gbp.log.info("On branch '%s', switching to '%s'" % (current, base))
        repo.set_branch(base)
        pq_branch = current
    else:
        pq_branch = pq_branch_name(current)
    spec = parse_spec(options, repo)
    upstream_commit = find_upstream_commit(repo, spec, options.upstream_tag)
    export_treeish = pq_branch

    update_patch_series(repo, spec, upstream_commit, export_treeish, options)

    GitCommand('status')(['--', spec.specdir])


def safe_patches(queue):
    """
    Safe the current patches in a temporary directory

    @param queue: an existing patch queue
    @return: safed queue (with patches in tmpdir)
    @rtype: tuple
    """

    tmpdir = tempfile.mkdtemp(prefix='patchimport_')
    safequeue = PatchSeries()

    if len(queue) > 0:
        gbp.log.debug("Safeing patches '%s' in '%s'" %
                      (os.path.dirname(queue[0].path), tmpdir))
    for patch in queue:
        base, _archive_fmt, comp = parse_archive_filename(patch.path)
        uncompressors = {'gzip': gzip.open, 'bzip2': bz2.BZ2File}
        if comp in uncompressors:
            gbp.log.debug("Uncompressing '%s'" % os.path.basename(patch.path))
            src = uncompressors[comp](patch.path, 'r')
            dst_name = os.path.join(tmpdir, os.path.basename(base))
        elif comp:
            raise GbpError("Unsupported patch compression '%s', giving up"
                           % comp)
        else:
            src = open(patch.path, 'r')
            dst_name = os.path.join(tmpdir, os.path.basename(patch.path))

        dst = open(dst_name, 'w')
        dst.writelines(src)
        src.close()
        dst.close()

        safequeue.append(patch)
        safequeue[-1].path = dst_name

    return safequeue


def get_packager(spec):
    """Get packager information from spec"""
    if spec.packager:
        match = re.match(r'(?P<name>.*[^ ])\s*<(?P<email>\S*)>',
                         spec.packager.strip())
        if match:
            return GitModifier(match.group('name'), match.group('email'))
    return GitModifier()


def import_spec_patches(repo, options):
    """
    apply a series of patches in a spec/packaging dir to branch
    the patch-queue branch for 'branch'

    @param repo: git repository to work on
    @param options: command options
    """
    current = repo.get_branch()
    # Get spec and related information
    if is_pq_branch(current):
        base = pq_branch_base(current)
        if options.force:
            spec = parse_spec(options, repo, base)
            spec_treeish = base
        else:
            raise GbpError("Already on a patch-queue branch '%s' - doing "
                           "nothing." % current)
    else:
        spec = parse_spec(options, repo)
        spec_treeish = None
        base = current
    upstream_commit = find_upstream_commit(repo, spec, options.upstream_tag)
    packager = get_packager(spec)
    pq_branch = pq_branch_name(base)

    # Create pq-branch
    if repo.has_branch(pq_branch) and not options.force:
        raise GbpError("Patch-queue branch '%s' already exists. "
                       "Try 'switch' instead." % pq_branch)
    try:
        if repo.get_branch() == pq_branch:
            repo.force_head(upstream_commit, hard=True)
        else:
            repo.create_branch(pq_branch, upstream_commit, force=True)
    except GitRepositoryError as err:
        raise GbpError("Cannot create patch-queue branch '%s': %s" %
                       (pq_branch, err))

    # Put patches in a safe place
    if spec_treeish:
        packaging_tmp = tempfile.mkdtemp(prefix='dump_')
        packaging_tree = '%s:%s' % (spec_treeish, options.packaging_dir)
        dump_tree(repo, packaging_tmp, packaging_tree, with_submodules=False,
                  recursive=False)
        spec.specdir = packaging_tmp
    in_queue = spec.patchseries()
    queue = safe_patches(in_queue)
    # Do import
    try:
        gbp.log.info("Switching to branch '%s'" % pq_branch)
        repo.set_branch(pq_branch)

        if not queue:
            return
        gbp.log.info("Trying to apply patches from branch '%s' onto '%s'" %
                     (base, upstream_commit))
        for patch in queue:
            gbp.log.debug("Applying %s" % patch.path)
            apply_and_commit_patch(repo, patch, packager)
    except (GbpError, GitRepositoryError) as err:
        repo.set_branch(base)
        repo.delete_branch(pq_branch)
        raise GbpError('Import failed: %s' % err)

    gbp.log.info("%d patches listed in '%s' imported on '%s'" % (len(queue), spec.specfile,
                                                                 pq_branch))


def rebase_pq(repo, options):
    """Rebase pq branch on the correct upstream version (from spec file)."""
    current = repo.get_branch()
    if is_pq_branch(current):
        base = pq_branch_base(current)
        spec = parse_spec(options, repo, base)
    else:
        base = current
        spec = parse_spec(options, repo)
    upstream_commit = find_upstream_commit(repo, spec, options.upstream_tag)

    switch_to_pq_branch(repo, base)
    GitCommand("rebase")([upstream_commit])


def usage_msg():
    return """%prog [options] action - maintain patches on a patch queue branch
Ations:
export         Export the patch queue / devel branch associated to the
               current branch into a patch series in and update the spec file
import         Create a patch queue / devel branch from spec file
               and patches in current dir.
rebase         Switch to patch queue / devel branch associated to the current
               branch and rebase against upstream.
drop           Drop (delete) the patch queue /devel branch associated to
               the current branch.
apply          Apply a patch
switch         Switch to patch-queue branch and vice versa."""


def build_parser(name):
    """Construct command line parser"""
    try:
        parser = GbpOptionParserRpm(command=os.path.basename(name),
                                    prefix='', usage=usage_msg())

    except GbpError as err:
        gbp.log.err(err)
        return None

    parser.add_boolean_config_file_option(option_name="patch-numbers",
                                          dest="patch_numbers")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      default=False, help="Verbose command execution")
    parser.add_option("--force", dest="force", action="store_true",
                      default=False,
                      help="In case of import even import if the branch already exists")
    parser.add_config_file_option(option_name="color", dest="color",
                                  type='tristate')
    parser.add_config_file_option(option_name="color-scheme",
                                  dest="color_scheme")
    parser.add_config_file_option(option_name="tmp-dir", dest="tmp_dir")
    parser.add_config_file_option(option_name="upstream-tag",
                                  dest="upstream_tag")
    parser.add_config_file_option(option_name="spec-file", dest="spec_file")
    parser.add_config_file_option(option_name="packaging-dir",
                                  dest="packaging_dir")
    return parser


def parse_args(argv):
    """Parse command line arguments"""
    parser = build_parser(argv[0])
    if not parser:
        return None, None
    return parser.parse_args(argv)


def main(argv):
    """Main function for the gbp pq-rpm command"""
    retval = 0

    (options, args) = parse_args(argv)
    if not options:
        return ExitCodes.parse_error

    gbp.log.setup(options.color, options.verbose, options.color_scheme)

    if len(args) < 2:
        gbp.log.err("No action given.")
        return 1
    else:
        action = args[1]

    if args[1] in ["export", "import", "rebase", "drop", "switch", "convert"]:
        pass
    elif args[1] in ["apply"]:
        if len(args) != 3:
            gbp.log.err("No patch name given.")
            return 1
        else:
            patchfile = args[2]
    else:
        gbp.log.err("Unknown action '%s'." % args[1])
        return 1

    try:
        repo = RpmGitRepository(os.path.curdir)
    except GitRepositoryError:
        gbp.log.err("%s is not a git repository" % (os.path.abspath('.')))
        return 1

    try:
        # Create base temporary directory for this run
        init_tmpdir(options.tmp_dir, prefix='pq-rpm_')
        current = repo.get_branch()
        if action == "export":
            export_patches(repo, options)
        elif action == "import":
            import_spec_patches(repo, options)
        elif action == "drop":
            drop_pq(repo, current)
        elif action == "rebase":
            rebase_pq(repo, options)
        elif action == "apply":
            patch = Patch(patchfile)
            apply_single_patch(repo, current, patch, fallback_author=None)
        elif action == "switch":
            switch_pq(repo, current)
    except KeyboardInterrupt:
        retval = 1
        gbp.log.err("Interrupted. Aborting.")
    except CommandExecFailed:
        retval = 1
    except GitRepositoryError as err:
        gbp.log.err("Git command failed: %s" % err)
        retval = 1
    except GbpError as err:
        if str(err):
            gbp.log.err(err)
        retval = 1
    finally:
        del_tmpdir()

    return retval


if __name__ == '__main__':
    sys.exit(main(sys.argv))
