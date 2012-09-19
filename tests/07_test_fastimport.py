# vim: set fileencoding=utf-8 :

"""Test L{FastImport} class"""

import os
import shutil

import gbp.log
import gbp.git

repo = None
fastimport = None
tmpdir = None
tf_name = 'testfile'
tl_name = 'a_testlink'

def setup():
    global repo, tmpdir

    gbp.log.setup(False, False)
    top = os.path.abspath(os.curdir)
    tmpdir = os.path.join(top,'gbp_%s_repo' % __name__)
    os.mkdir(tmpdir)

    repodir = os.path.join(tmpdir, 'test_repo')
    repo = gbp.git.GitRepository.create(repodir)

def teardown():
    if not os.getenv("GBP_TESTS_NOCLEAN") and tmpdir:
        shutil.rmtree(tmpdir)

def test_init_fastimport():
    """Create a fastimport object"""
    global fastimport
    fastimport = gbp.git.FastImport(repo)
    assert fastimport, "Failed to init FastImport"

def test_add_file():
    """Add a file via fastimport"""
    author = repo.get_author_info()
    fastimport.start_commit('master', author, "a commit")
    fastimport.deleteall()
    testfile = os.path.join(repo.path, '.git', 'description')
    fastimport.add_file('./testfile',
                        file(testfile),
                        os.path.getsize(testfile))

def test_add_symlink():
    """Add a symbolic link via fastimport"""
    author = repo.get_author_info()
    fastimport.start_commit('master', author, "a 2nd commit")
    fastimport.add_symlink(tl_name, tf_name)

def test_close():
    fastimport.close()

def test_result():
    repo.force_head('master', hard=True)

    testfile = os.path.join(repo.path, tf_name)
    testlink = os.path.join(repo.path, tl_name)

    assert os.path.exists(testfile), "%s doesn't exist" % testfile
    assert os.path.lexists(testlink), "%s doesn't exist" % testlink
    assert os.readlink(testlink) == tf_name

