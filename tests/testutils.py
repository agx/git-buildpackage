# vim: set fileencoding=utf-8 :

import os
import shutil
import unittest

import gbp.log
import gbp.deb.git
import gbp.errors

class DebianGitTestRepo(unittest.TestCase):
    """Scratch repo for a single test"""

    def setUp(self):
        gbp.log.setup(False, False)
        top = os.path.abspath(os.path.curdir)
        self.tmpdir = os.path.join(top, 'gbp_%s_repo' % __name__)
        os.mkdir(self.tmpdir)

        repodir = os.path.join(self.tmpdir, 'test_repo')
        self.repo = gbp.deb.git.DebianGitRepository.create(repodir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def add_file(self, name, content=None, msg=None):
        """
        Add a single file with name I{name} and content I{content}. If
        I{content} is C{none} the content of the file is undefined.

        @param name: the file's path relativ to the git repo
        @type name: C{str}
        @param content: the file's content
        @type content: C{str}
        """
        path = os.path.join(self.repo.path, name)

        d = os.path.dirname(path)
        if not os.path.exists(d):
            os.makedirs(d)

        with file(path, 'w+') as f:
            content == None or f.write(content)
        self.repo.add_files(name, force=True)
        self.repo.commit_files(path, msg or "added %s" % name)
