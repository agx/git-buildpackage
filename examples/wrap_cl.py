# Simple changelog entry formatter
#
# It simply uses the built in formatter and linewraps the text
#
# Use git-dch --customizations=/usr/share/doc/git-buildpackage/examples/wrap_cl.py
# or set it via gbp.conf

import textwrap
import gbp.dch


def format_changelog_entry(commit_info, options, last_commit=False):
    entry = gbp.dch.format_changelog_entry(commit_info, options, last_commit)
    if entry:
        return textwrap.wrap(" ".join(entry))
