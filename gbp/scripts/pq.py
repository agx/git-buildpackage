# vim: set fileencoding=utf-8 :
#
# (C) 2011 Guido Günther <agx@sigxcpu.org>
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
"""manage patches in a patch queue"""

import errno
import os
import shutil
import sys
import tempfile
from gbp.config import GbpOptionParserDebian
from gbp.git import (GitRepositoryError, GitRepository)
from gbp.command_wrappers import (GitCommand, CommandExecFailed)
from gbp.errors import GbpError
import gbp.log
from gbp.patch_series import (PatchSeries, Patch)
from gbp.scripts.common.pq import (is_pq_branch, pq_branch_name, pq_branch_base,
                                 write_patch, switch_to_pq_branch,
                                 apply_single_patch, apply_and_commit_patch,
                                 drop_pq, get_maintainer_from_control)

PATCH_DIR = "debian/patches/"
SERIES_FILE = os.path.join(PATCH_DIR,"series")


def export_patches(repo, branch, options):
    """Export patches from the pq branch into a patch series"""
    if is_pq_branch(branch):
        base = pq_branch_base(branch)
        gbp.log.info("On '%s', switching to '%s'" % (branch, base))
        branch = base
        repo.set_branch(branch)

    pq_branch = pq_branch_name(branch)
    try:
        shutil.rmtree(PATCH_DIR)
    except OSError as (e, msg):
        if e != errno.ENOENT:
            raise GbpError("Failed to remove patch dir: %s" % msg)
        else:
            gbp.log.debug("%s does not exist." % PATCH_DIR)

    patches = repo.format_patches(branch, pq_branch, PATCH_DIR,
                                  signature=False)
    if patches:
        f = file(SERIES_FILE, 'w')
        gbp.log.info("Regenerating patch queue in '%s'." % PATCH_DIR)
        for patch in patches:
            filename = write_patch(patch, PATCH_DIR, options)
            f.write(filename[len(PATCH_DIR):] + '\n')

        f.close()
        GitCommand('status')(['--', PATCH_DIR])
    else:
        gbp.log.info("No patches on '%s' - nothing to do." % pq_branch)


def safe_patches(series):
    """
    Safe the current patches in a temporary directory
    below .git/

    @param series: path to series file
    @return: tmpdir and path to safed series file
    @rtype: tuple
    """

    src = os.path.dirname(series)
    name = os.path.basename(series)

    tmpdir = tempfile.mkdtemp(dir='.git/', prefix='gbp-pq')
    patches = os.path.join(tmpdir, 'patches')
    series = os.path.join(patches, name)

    gbp.log.debug("Safeing patches '%s' in '%s'" % (src, tmpdir))
    shutil.copytree(src, patches)

    return (tmpdir, series)


def import_quilt_patches(repo, branch, series, tries, force):
    """
    apply a series of quilt patches in the series file 'series' to branch
    the patch-queue branch for 'branch'

    @param repo: git repository to work on
    @param branch: branch to base pqtch queue on
    @param series; series file to read patches from
    @param tries: try that many times to apply the patches going back one
                  commit in the branches history after each failure.
    @param force: import the patch series even if the branch already exists
    """
    tmpdir = None

    if is_pq_branch(branch):
        if force:
            branch = pq_branch_base(branch)
            pq_branch = pq_branch_name(branch)
            repo.checkout(branch)
        else:
            gbp.log.err("Already on a patch-queue branch '%s' - doing nothing." % branch)
            raise GbpError
    else:
        pq_branch = pq_branch_name(branch)

    if repo.has_branch(pq_branch):
        if force:
            drop_pq(repo, branch)
        else:
            raise GbpError("Patch queue branch '%s'. already exists. Try 'rebase' instead."
                           % pq_branch)

    commits = repo.get_commits(num=tries, first_parent=True)
    # If we go back in history we have to safe our pq so we always try to apply
    # the latest one
    if len(commits) > 1:
        tmpdir, series = safe_patches(series)

    queue = PatchSeries.read_series_file(series)

    i = len(commits)
    for commit in commits:
        if len(commits):
            gbp.log.info("%d %s left" % (i, 'tries' if i > 1 else 'try'))
        try:
            gbp.log.info("Trying to apply patches at '%s'" % commit)
            repo.create_branch(pq_branch, commit)
        except GitRepositoryError:
            raise GbpError("Cannot create patch-queue branch '%s'." % pq_branch)

        repo.set_branch(pq_branch)
        for patch in queue:
            gbp.log.debug("Applying %s" % patch.path)
            try:
                apply_and_commit_patch(repo, patch,
                                       get_maintainer_from_control,
                                       patch.topic)
            except (GbpError, GitRepositoryError):
                repo.set_branch(branch)
                repo.delete_branch(pq_branch)
                break
        else:
            # All patches applied successfully
            break
        i-=1
    else:
        raise GbpError("Couldn't apply patches")

    if tmpdir:
        gbp.log.debug("Remove temporary patch safe '%s'" % tmpdir)
        shutil.rmtree(tmpdir)


def rebase_pq(repo, branch):
    if is_pq_branch(branch):
        base = pq_branch_base(branch)
    else:
        switch_to_pq_branch(repo, branch)
        base = branch
    GitCommand("rebase")([base])


def switch_pq(repo, current):
    """Switch to patch-queue branch if on base branch and vice versa"""
    if is_pq_branch(current):
        base = pq_branch_base(current)
        gbp.log.info("Switching to %s" % base)
        repo.checkout(base)
    else:
        switch_to_pq_branch(repo, current)


def main(argv):
    retval = 0

    parser = GbpOptionParserDebian(command=os.path.basename(argv[0]), prefix='',
                                   usage="%prog [options] action - maintain patches on a patch queue branch\n"
        "Actions:\n"
        "  export         export the patch queue associated to the current branch\n"
        "                 into a quilt patch series in debian/patches/ and update the\n"
        "                 series file.\n"
        "  import         create a patch queue branch from quilt patches in debian/patches.\n"
        "  rebase         switch to patch queue branch associated to the current\n"
        "                 branch and rebase against current branch.\n"
        "  drop           drop (delete) the patch queue associated to the current branch.\n"
        "  apply          apply a patch\n"
        "  switch         switch to patch-queue branch and vice versa")
    parser.add_boolean_config_file_option(option_name="patch-numbers", dest="patch_numbers")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_option("--topic", dest="topic", help="in case of 'apply' topic (subdir) to put patch into")
    parser.add_config_file_option(option_name="time-machine", dest="time_machine", type="int")
    parser.add_option("--force", dest="force", action="store_true", default=False,
                      help="in case of import even import if the branch already exists")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')

    (options, args) = parser.parse_args(argv)
    gbp.log.setup(options.color, options.verbose)

    if len(args) < 2:
        gbp.log.err("No action given.")
        return 1
    else:
        action = args[1]

    if args[1] in ["export", "import", "rebase", "drop", "switch"]:
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
        repo = GitRepository(os.path.curdir)
    except GitRepositoryError:
        gbp.log.err("%s is not a git repository" % (os.path.abspath('.')))
        return 1

    try:
        current = repo.get_branch()
        if action == "export":
            export_patches(repo, current, options)
        elif action == "import":
            series = SERIES_FILE
            tries = options.time_machine if (options.time_machine > 0) else 1
            import_quilt_patches(repo, current, series, tries, options.force)
            current = repo.get_branch()
            gbp.log.info("Patches listed in '%s' imported on '%s'" %
                          (series, current))
        elif action == "drop":
            drop_pq(repo, current)
        elif action == "rebase":
            rebase_pq(repo, current)
        elif action == "apply":
            patch = Patch(patchfile)
            apply_single_patch(repo, current, patch,
                               get_maintainer_from_control,
                               options.topic)
        elif action == "switch":
            switch_pq(repo, current)
    except CommandExecFailed:
        retval = 1
    except (GbpError, GitRepositoryError) as err:
        if len(err.__str__()):
            gbp.log.err(err)
        retval = 1

    return retval

if __name__ == '__main__':
    sys.exit(main(sys.argv))

