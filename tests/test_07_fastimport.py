# vim: set fileencoding=utf-8 :

"""Test L{FastImport} class"""

from . import context

import os
import unittest

import gbp.log
import gbp.git

tf_name = 'testfile'
tl_name = 'a_testlink'


class TestFastImport(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        tmpdir = context.new_tmpdir(__name__)
        self.repo = gbp.git.GitRepository.create(tmpdir.join('test_repo'))
        self.fastimport = gbp.git.FastImport(self.repo)
        assert self.fastimport, "Failed to init FastImport"

    @classmethod
    def tearDownClass(self):
        self.fastimport.close()

        self.repo.force_head('master', hard=True)

        testfile = os.path.join(self.repo.path, tf_name)
        testlink = os.path.join(self.repo.path, tl_name)

        assert os.path.exists(testfile), "%s doesn't exist" % testfile
        assert os.path.lexists(testlink), "%s doesn't exist" % testlink
        assert os.readlink(testlink) == tf_name

        context.teardown()

    def test_add_file(self):
        """Add a file via fastimport"""
        author = self.repo.get_author_info()
        self.fastimport.start_commit('master', author, "a commit")
        self.fastimport.deleteall()
        testfile = os.path.join(self.repo.path, '.git', 'description')
        self.fastimport.add_file(b'./testfile',
                                 open(testfile, 'rb'),
                                 os.path.getsize(testfile))

    def test_add_symlink(self):
        """Add a symbolic link via fastimport"""
        author = self.repo.get_author_info()
        self.fastimport.start_commit('master', author, "a 2nd commit")
        self.fastimport.add_symlink(tl_name, tf_name)
