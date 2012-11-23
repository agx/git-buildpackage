# vim: set fileencoding=utf-8 :
#
# (C) 2011 Guido Günther <agx@sigxcpu.org>
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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""Common functionality for Debian and RPM patchqueue management"""

import re
import os
import shutil
import subprocess
from gbp.git import GitRepositoryError
from gbp.errors import GbpError
import gbp.log

PQ_BRANCH_PREFIX = "patch-queue/"


def is_pq_branch(branch):
    """
    is branch a patch-queue branch?

    >>> is_pq_branch("foo")
    False
    >>> is_pq_branch("patch-queue/foo")
    True
    """
    return [False, True][branch.startswith(PQ_BRANCH_PREFIX)]


def pq_branch_name(branch):
    """
    get the patch queue branch corresponding to branch

    >>> pq_branch_name("patch-queue/master")
    >>> pq_branch_name("foo")
    'patch-queue/foo'
    """
    if not is_pq_branch(branch):
        return PQ_BRANCH_PREFIX + branch


def pq_branch_base(pq_branch):
    """
    get the branch corresponding to the given patch queue branch

    >>> pq_branch_base("patch-queue/master")
    'master'
    >>> pq_branch_base("foo")
    """
    if is_pq_branch(pq_branch):
        return pq_branch[len(PQ_BRANCH_PREFIX):]


def write_patch(patch, patch_dir, options):
    """Write the patch exported by 'git-format-patch' to it's final location
       (as specified in the commit)"""
    oldname = os.path.basename(patch)
    newname = oldname
    tmpname = patch + ".gbp"
    old = file(patch, 'r')
    tmp = file(tmpname, 'w')
    topic = None

    # Skip first line (From <sha1>)
    old.readline()
    for line in old:
        if line.lower().startswith("gbp-pq-topic: "):
            topic = line.split(" ", 1)[1].strip()
            gbp.log.debug("Topic %s found for %s" % (topic, patch))
            continue
        tmp.write(line)
    tmp.close()
    old.close()

    if not options.patch_numbers:
        patch_re = re.compile("[0-9]+-(?P<name>.+)")
        m = patch_re.match(oldname)
        if m:
            newname = m.group('name')

    if topic:
        topicdir = os.path.join(patch_dir, topic)
    else:
        topicdir = patch_dir

    if not os.path.isdir(topicdir):
        os.makedirs(topicdir, 0755)

    os.unlink(patch)
    dstname = os.path.join(topicdir, newname)
    gbp.log.debug("Moving %s to %s" % (tmpname, dstname))
    shutil.move(tmpname, dstname)

    return dstname


def get_maintainer_from_control(repo):
    """Get the maintainer from the control file"""
    control = os.path.join(repo.path, 'debian', 'control')

    cmd = 'sed -n -e \"s/Maintainer: \\+\\(.*\\)/\\1/p\" %s' % control
    cmdout = subprocess.Popen(cmd, shell=True,
                              stdout=subprocess.PIPE).stdout.readlines()

    if len(cmdout) > 0:
        maintainer = cmdout[0].strip()
        m = re.match('(?P<name>.*[^ ]) *<(?P<email>.*)>', maintainer)
        if m:
            return m.group('name'), m.group('email')

    return None, None


def switch_to_pq_branch(repo, branch):
    """
    Switch to patch-queue branch if not already there, create it if it
    doesn't exist yet
    """
    if is_pq_branch(branch):
        return

    pq_branch = pq_branch_name(branch)
    if not repo.has_branch(pq_branch):
        try:
            repo.create_branch(pq_branch)
        except GitRepositoryError:
            raise GbpError("Cannot create patch-queue branch '%s'. "
                           "Try 'rebase' instead." % pq_branch)

    gbp.log.info("Switching to '%s'" % pq_branch)
    repo.set_branch(pq_branch)


def apply_single_patch(repo, branch, patch, get_author_info, topic=None):
    switch_to_pq_branch(repo, branch)
    apply_and_commit_patch(repo, patch, get_author_info, topic)


def apply_and_commit_patch(repo, patch, get_author_info, topic=None):
    """apply a single patch 'patch', add topic 'topic' and commit it"""
    author = {'name': patch.author,
              'email': patch.email,
              'date': patch.date }

    patch_fn = os.path.basename(patch.path)
    if not (patch.author and patch.email):
        name, email = get_author_info(repo)
        if name:
            gbp.log.warn("Patch '%s' has no authorship information, "
                         "using '%s <%s>'" % (patch_fn, name, email))
            author['name'] = name
            author['email'] = email
        else:
            gbp.log.warn("Patch '%s' has no authorship information" % patch_fn)

    repo.apply_patch(patch.path, strip=patch.strip)
    tree = repo.write_tree()
    msg = "%s\n\n%s" % (patch.subject, patch.long_desc)
    if topic:
        msg += "\nGbp-Pq-Topic: %s" % topic
    commit = repo.commit_tree(tree, msg, [repo.head], author=author)
    repo.update_ref('HEAD', commit, msg="gbp-pq import %s" % patch.path)


def drop_pq(repo, branch):
    if is_pq_branch(branch):
        gbp.log.err("On a patch-queue branch, can't drop it.")
        raise GbpError
    else:
        pq_branch = pq_branch_name(branch)

    if repo.has_branch(pq_branch):
        repo.delete_branch(pq_branch)
        gbp.log.info("Dropped branch '%s'." % pq_branch)
    else:
        gbp.log.info("No patch queue branch found - doing nothing.")
