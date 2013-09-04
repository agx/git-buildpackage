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
import subprocess
import datetime
import time
from email.message import Message
from email.header import Header
from email.charset import Charset, QP

from gbp.git import GitRepositoryError
from gbp.git.modifier import GitModifier, GitTz
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


def parse_gbp_commands(info, cmd_tag, noarg_cmds, arg_cmds):
    """Parse gbp commands from commit message"""
    cmd_re = re.compile(r'^%s:\s*(?P<cmd>[a-z-]+)(\s+(?P<args>\S.*))?' %
                            cmd_tag, flags=re.I)
    commands = {}
    for line in info['body'].splitlines():
        match = re.match(cmd_re, line)
        if match:
            cmd = match.group('cmd').lower()
            if arg_cmds and cmd in arg_cmds:
                if match.group('args'):
                    commands[cmd] = match.group('args')
                else:
                    gbp.log.warn("Ignoring gbp-command '%s' in commit %s: "
                                 "missing cmd arguments" % (line, info['id']))
            elif noarg_cmds and cmd in noarg_cmds:
                commands[cmd] = match.group('args')
            else:
                gbp.log.warn("Ignoring unknow gbp-command '%s' in commit %s"
                                % (line, info['id']))
    return commands


def patch_path_filter(file_status, exclude_regex=None):
    """
    Create patch include paths, i.e. a "negation" of the exclude paths.
    """
    if exclude_regex:
        include_paths = []
        for file_list in file_status.values():
            for fname in file_list:
                if not re.match(exclude_regex, fname):
                    include_paths.append(fname)
    else:
        include_paths = ['.']

    return include_paths


def write_patch_file(filename, commit_info, diff):
    """Write patch file"""
    if not diff:
        gbp.log.debug("I won't generate empty diff %s" % filename)
        return None
    try:
        with open(filename, 'w') as patch:
            msg = Message()
            charset = Charset('utf-8')
            charset.body_encoding = None
            charset.header_encoding = QP

            # Write headers
            name = commit_info['author']['name']
            email = commit_info['author']['email']
            # Git compat: put name in quotes if special characters found
            if re.search("[,.@()\[\]\\\:;]", name):
                name = '"%s"' % name
            from_header = Header(unicode(name, 'utf-8'), charset, 77, 'from')
            from_header.append(unicode('<%s>' % email))
            msg['From'] = from_header
            date = commit_info['author'].datetime
            datestr = date.strftime('%a, %-d %b %Y %H:%M:%S %z')
            msg['Date'] = Header(unicode(datestr, 'utf-8'), charset, 77, 'date')
            msg['Subject'] = Header(unicode(commit_info['subject'], 'utf-8'),
                                    charset, 77, 'subject')
            # Write message body
            if commit_info['body']:
                # Strip extra linefeeds
                body = commit_info['body'].rstrip() + '\n'
                try:
                    msg.set_payload(body.encode('ascii'))
                except UnicodeDecodeError:
                    msg.set_payload(body, charset)
            patch.write(msg.as_string(unixfrom=False))

            # Write diff
            patch.write('---\n')
            patch.write(diff)
    except IOError as err:
        raise GbpError('Unable to create patch file: %s' % err)
    return filename


def format_patch(outdir, repo, commit_info, series, numbered=True,
                 topic_regex=None, path_exclude_regex=None, topic=''):
    """Create patch of a single commit"""
    commit = commit_info['id']

    # Parse and filter commit message body
    mangled_body = ""
    for line in commit_info['body'].splitlines():
        if topic_regex:
            match = re.match(topic_regex, line, flags=re.I)
            if match:
                topic = match.group('topic')
                gbp.log.debug("Topic %s found for %s" % (topic, commit))
                continue
        mangled_body += line + '\n'
    commit_info['body'] = mangled_body

    # Determine filename and path
    outdir = os.path.join(outdir, topic)
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    num_prefix = '%04d-' % (len(series) + 1)
    suffix = '.patch'
    base_maxlen = 63 - len(num_prefix) - len(suffix)
    base = commit_info['patchname'][:base_maxlen]
    filename = (num_prefix if numbered else '') + base + suffix
    filepath = os.path.join(outdir, filename)
    # Make sure that we don't overwrite existing patches in the series
    if filepath in series:
        presuffix = '-%d' % len(series)
        base = base[:base_maxlen-len(presuffix)] + presuffix
        filename = (num_prefix if numbered else '') + base + suffix
        filepath = os.path.join(outdir, filename)

    # Determine files to include
    paths = patch_path_filter(commit_info['files'], path_exclude_regex)

    # Finally, create the patch
    patch = None
    if paths:
        diff = repo.diff('%s^!' % commit, paths=paths, stat=80, summary=True,
                         text=True)
        patch = write_patch_file(filepath, commit_info, diff)
        if patch:
            series.append(patch)
    return patch


def format_diff(outdir, filename, repo, start, end, path_exclude_regex=None):
    """Create a patch of diff between two repository objects"""

    info = {'author': repo.get_author_info()}
    now = datetime.datetime.now().replace(tzinfo=GitTz(-time.timezone))
    info['author'].set_date(now)
    info['subject'] = "Raw diff %s..%s" % (start, end)
    info['body'] = ("Raw diff between %s '%s' and\n%s '%s'\n" %
                    (repo.get_obj_type(start), start,
                    repo.get_obj_type(end), end))
    if not filename:
        filename = '%s-to-%s.diff' % (start, end)
    filename = os.path.join(outdir, filename)

    file_status = repo.diff_status(start, end)
    paths = patch_path_filter(file_status, path_exclude_regex)
    if paths:
        diff = repo.diff(start, end, paths=paths, stat=80, summary=True,
                         text=True)
        return write_patch_file(filename, info, diff)
    return None


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
            return GitModifier(m.group('name'), m.group('email'))

    return GitModifier()


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


def apply_single_patch(repo, branch, patch, fallback_author, topic=None):
    switch_to_pq_branch(repo, branch)
    apply_and_commit_patch(repo, patch, fallback_author, topic)


def apply_and_commit_patch(repo, patch, fallback_author, topic=None):
    """apply a single patch 'patch', add topic 'topic' and commit it"""
    author = {'name': patch.author,
              'email': patch.email,
              'date': patch.date }

    patch_fn = os.path.basename(patch.path)
    if not (author['name'] and author['email']):
        if fallback_author and fallback_author['name']:
            author = fallback_author
            gbp.log.warn("Patch '%s' has no authorship information, using "
                         "'%s <%s>'" % (patch_fn, author['name'],
                                        author['email']))
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
