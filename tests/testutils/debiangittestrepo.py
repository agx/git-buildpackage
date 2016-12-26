# vim: set fileencoding=utf-8 :

from .. import context

import os
import unittest

import gbp.deb.git


class DebianGitTestRepo(unittest.TestCase):
    """Scratch repo for a single unit test"""

    def setUp(self, repo_cls=None):
        name = 'test_repo'
        self.tmpdir = context.new_tmpdir(__name__)

        if repo_cls is None:
            repo_cls = gbp.deb.git.DebianGitRepository

        repodir = self.tmpdir.join(name)
        self.repodir = os.path.join(str(self.tmpdir), name)
        self.repo = repo_cls.create(repodir)

    def tearDown(self):
        context.teardown()

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

        with open(path, 'w+') as f:
            content is None or f.write(content)
        self.repo.add_files(name, force=True)
        self.repo.commit_files(path, msg or "added %s" % name)
