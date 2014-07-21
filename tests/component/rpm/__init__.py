# vim: set fileencoding=utf-8 :
#
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
"""Test module for RPM command line tools of the git-buildpackage suite"""

from nose.tools import nottest
import os
import shutil
from xml.dom import minidom

from gbp.git import GitRepository, GitRepositoryError

from tests.component import ComponentTestBase, ComponentTestGitRepository


RPM_TEST_DATA_SUBMODULE = os.path.join('tests', 'component', 'rpm', 'data')
RPM_TEST_DATA_DIR = os.path.abspath(RPM_TEST_DATA_SUBMODULE)

class RepoManifest(object):
    """Class representing a test repo manifest file"""
    def __init__(self, filename=None):
        self._doc = minidom.Document()
        if filename:
            self._doc = minidom.parse(filename)
            # Disable "Instance of 'Document' has no 'firstChild' member"
            # pylint: disable=E1103
            if self._doc.firstChild.nodeName != 'gbp-test-manifest':
                raise Exception('%s is not a test repo manifest' % filename)
            # pylint: enable=E1103
        else:
            self._doc.appendChild(self._doc.createElement("gbp-test-manifest"))

    def projects_iter(self):
        """Return an iterator over projects"""
        for prj_e in self._doc.getElementsByTagName('project'):
            branches = {}
            for br_e in prj_e.getElementsByTagName('branch'):
                rev = br_e.getAttribute('revision')
                branches[br_e.getAttribute('name')] = rev
            yield prj_e.getAttribute('name'), branches


    def write(self, filename):
        """Write to file"""
        with open(filename, 'w') as fileobj:
            fileobj.write(self._doc.toprettyxml())

def setup():
    """Test Module setup"""
    ComponentTestGitRepository.check_testdata(RPM_TEST_DATA_SUBMODULE)


class RpmRepoTestBase(ComponentTestBase):
    """Baseclass for tests run in a Git repository with packaging data"""

    @classmethod
    def setup_class(cls):
        """Initializations only made once per test run"""
        super(RpmRepoTestBase, cls).setup_class()
        cls.manifest = RepoManifest(os.path.join(RPM_TEST_DATA_DIR,
                                                 'test-repo-manifest.xml'))
        cls.orig_repos = {}
        for prj, brs in cls.manifest.projects_iter():
            repo = GitRepository.create(os.path.join(cls._tmproot,
                                        '%s.repo' % prj))
            try:
                repo.add_remote_repo('origin', RPM_TEST_DATA_DIR, fetch=True)
            except GitRepositoryError:
                # Workaround for older git working on submodules initialized
                # with newer git
                gitfile = os.path.join(RPM_TEST_DATA_DIR, '.git')
                if os.path.isfile(gitfile):
                    with open(gitfile) as fobj:
                        link = fobj.readline().replace('gitdir:', '').strip()
                    link_dir = os.path.join(RPM_TEST_DATA_DIR, link)
                    repo.remove_remote_repo('origin')
                    repo.add_remote_repo('origin', link_dir, fetch=True)
                else:
                    raise
            # Fetch all remote refs of the orig repo, too
            repo.fetch('origin', tags=True,
                       refspec='refs/remotes/*:refs/upstream/*')
            for branch, rev in brs.iteritems():
                repo.create_branch(branch, rev)
            repo.force_head('master', hard=True)
            cls.orig_repos[prj] = repo

    @classmethod
    @nottest
    def init_test_repo(cls, pkg_name):
        """Initialize git repository for testing"""
        dirname = os.path.basename(cls.orig_repos[pkg_name].path)
        shutil.copytree(cls.orig_repos[pkg_name].path, dirname)
        os.chdir(dirname)
        return GitRepository('.')

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
