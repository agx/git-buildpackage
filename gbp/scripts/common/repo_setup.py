# vim: set fileencoding=utf-8 :
#
# (C) 2006-2011, 2016 Guido Guenther <agx@sigxcpu.org>
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


def set_user_name_and_email(repo_user, repo_email, repo):
    if repo_user == 'DEBIAN':
        if os.getenv('DEBFULLNAME'):
            repo.set_user_name(os.getenv('DEBFULLNAME'))

    if repo_email == 'DEBIAN':
        if os.getenv('DEBEMAIL'):
            repo.set_user_email(os.getenv('DEBEMAIL'))
