#! /usr/bin/python
# vim: set fileencoding=utf-8 :
#
# (C) 2010 Guido Guenther <agx@sigxcpu.org>
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
# Simple Zeitgeist Git data source

"""Post-commit hook to submit the commit to Zeitgeist (http://www.zeitgeist-project.com)

copy as post-commit to

    .git/hooks/post-commit

in existing repositories or to

    /usr/share/git-core/templates

so it get's used for new ones.
"""


import os
import subprocess
import sys
import time

CLIENT = None

try:
    from zeitgeist.client import ZeitgeistClient
    from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation
except ImportError:
    pass
else:
    try:
        CLIENT = ZeitgeistClient()
    except RuntimeError as e:
        print("Unable to connect to Zeitgeist, won't send events. Reason: '%s'" % e)


def get_repo():
    """Get uri of remote repository and its name"""
    repo = None
    uri = subprocess.Popen(['git', 'config', '--get', 'remote.origin.url'],
                           stdout=subprocess.PIPE).communicate()[0]

    if uri:
        uri = uri.strip().decode(sys.getfilesystemencoding())
        if '/' in uri:
            sep = '/'
        else:
            sep = ':'
        try:
            repo = unicode(uri.rsplit(sep, 1)[1])
        except IndexError:  # no known separator
            repo = uri
        repo = repo.rsplit(u'.git', 1)[0]
    return repo, uri


def main(argv):
    interpretation = Interpretation.MODIFY_EVENT.uri

    # FIXME: I'd be great if zeitgeist would allow for more detail:
    #           * branch
    #           * log summary (git log -1 --format=%s HEAD)
    curdir = os.path.abspath(os.curdir).decode(sys.getfilesystemencoding())
    uri = u"file://%s" % curdir

    repo, origin = get_repo()
    if not repo:
        repo = unicode(curdir.rsplit('/', 1)[1])
        origin = uri

    subject = Subject.new_for_values(
        uri=uri,
        interpretation=Interpretation.DOCUMENT.TEXT_DOCUMENT.PLAIN_TEXT_DOCUMENT.SOURCE_CODE.uri,
        manifestation=Manifestation.FILE_DATA_OBJECT.uri,
        text=repo,
        origin=origin)
    event = Event.new_for_values(
        timestamp=int(time.time() * 1000),
        interpretation=interpretation,
        manifestation=Manifestation.USER_ACTIVITY.uri,
        actor="application://gitg.desktop",
        subjects=[subject])
    CLIENT.insert_event(event)


if __name__ == '__main__':
    main(sys.argv)
