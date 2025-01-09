# vim: set fileencoding=utf-8 :
#
# (C) 2006-2011, 2016 Guido Günther <agx@sigxcpu.org>
# (C) 2021 Andrej Shadura <andrew@shadura.me>
# (C) 2021 Collabora Limited
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
"""Common repository setup functionality."""

import os
import re
import gbp.log

from pathlib import Path


def set_user_name_and_email(repo_user, repo_email, repo):
    if repo_user == 'DEBIAN':
        if os.getenv('DEBFULLNAME'):
            repo.set_user_name(os.getenv('DEBFULLNAME'))

    if repo_email == 'DEBIAN':
        if os.getenv('DEBEMAIL'):
            repo.set_user_email(os.getenv('DEBEMAIL'))


def check_gitattributes(repo, treeish) -> bool:
    """
    Verify the treeish doesn’t contain non-empty .gitattributes files.
    """
    for mode, _type, sha1, size, path in repo.list_tree(treeish, recurse=True, sizes=True):
        if size == 0:
            continue
        if path == b'.gitattributes' or path.endswith(b'/.gitattributes'):
            gbp.log.debug("Found non-empty .gitattributes: %s" % path)
            return False
    return True


dgit_attr_macro_re = re.compile(r'^\[attr\]dgit-defuse-attrs\s')
dgit_attr_macro_defn = '-text -eol -crlf -ident -filter -working-tree-encoding'
attr_glob_defns = {
    'dgit-defuse-attrs',
    '-export-subst',
    '-export-ignore',
}


def is_gitattributes_set_up(repo) -> bool:
    """
    Return True if git attributes have been set up correctly:
        - dgit-defuse-attrs macro exists
        - dgit-defuse-attrs includes attributes we’re interested in
        - dgit-defuse-attrs is enabled for *
        - export-subst and export-ignore are unset for *
    """
    gitattrs = Path(repo.git_dir) / 'info' / 'attributes'
    if not gitattrs.exists():
        return False
    dgit_macro_present = False
    attrs = set()
    for line in gitattrs.read_text().splitlines():
        if dgit_attr_macro_re.match(line):
            gbp.log.debug("Found Git attribute macro: %s" % line)
            dgit_macro_present = line.endswith(dgit_attr_macro_defn)
            continue
        attr = line.split()
        if attr[0] == '*' and len(attr) == 2:
            attrs.add(attr[1])
    gbp.log.debug("Found global Git attributes: %s" % ', '.join(attrs))
    return dgit_macro_present and attrs >= attr_glob_defns


def setup_gitattributes(repo, treeish='HEAD'):
    """
    Setup .git/info/attributes in a way to prevent transformations from interfering
    with packaging, because the working tree files can differ from the Git revision
    history (and from the source packages).

    Similar functionality has been implemented by dgit and git-deborig, so we try
    to stay compatible and re-use the name of the attribute macro. Since dgit doesn’t
    disable export-subst and export-ignore, which may interfere with export-orig, we
    add this on top the same way git-deborig does.
    """
    if is_gitattributes_set_up(repo):
        return
    gbp.log.debug("Configuring Git attributes")
    gitattrs = Path(repo.git_dir) / 'info' / 'attributes'
    new_attributes = []
    if not gitattrs.exists():
        gitattrs.parent.mkdir(exist_ok=True)
    else:
        for line in gitattrs.read_text().splitlines():
            attr = line.split()
            if attr[0] == '*' and len(attr) == 2:
                if attr[1] in attr_glob_defns:
                    continue
            if dgit_attr_macro_re.match(line):
                new_attributes += [
                    "# Old dgit macro disabled:",
                    "# %s" % line,
                ]
                gbp.log.debug("Disabling old dgit macro: '%s'" % line)
            else:
                new_attributes.append(line)
    new_attributes += [
        "# Added by git-buildpackage to disable .gitattributes found in the upstream tree",
        "[attr]dgit-defuse-attrs  %s" % dgit_attr_macro_defn,
    ] + ['* %s' % attr for attr in attr_glob_defns]
    newattrs = gitattrs.with_suffix('.new')
    newattrs.write_text('\n'.join(new_attributes))
    newattrs.rename(gitattrs)
