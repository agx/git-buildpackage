# vim: set fileencoding=utf-8 :
"""
Test pristine-tar related methods in

    - L{gbp.deb.pristinetar.DebianPristineTar}

and

    - L{gbp.deb.git.DebianGitRepository}

This testcase creates this reposity:

    - A repository at I{dirs['repo']} called I{repo}

"""

import os
from .. import context

test_data = os.path.join(context.projectdir, "tests/data/pristine_tar")
dirs = {}


def setup_module():
    dirs['repo'] = context.new_tmpdir(__name__).join('repo')


def teardown_module():
    del dirs['repo']
    context.teardown()


def test_pristine_tar():
    """
    >>> setup_module()
    >>> import os, gbp.deb.git
    >>> repo = gbp.deb.git.DebianGitRepository.create(dirs['repo'])
    >>> # test_empty_repo():
    >>> # Empty repos have no branch pristine-tar branch
    >>> repo = gbp.deb.git.DebianGitRepository(dirs['repo'])
    >>> repo.has_pristine_tar_branch()
    False
    >>> repo.pristine_tar.has_commit('upstream', '1.0', 'gzip')
    False
    >>> # test_commit_dir():
    >>> # Empty repos have no branch pristine-tar branch
    >>> repo = gbp.deb.git.DebianGitRepository(dirs['repo'])
    >>> commit = repo.commit_dir(test_data, msg="initial commit", branch=None)
    >>> repo.create_branch('upstream')
    >>> # test_create_tarball():
    >>> # Create a tarball from a git tree and add a stub signature
    >>> repo = gbp.deb.git.DebianGitRepository(dirs['repo'])
    >>> repo.archive('tar', 'upstream/', '../upstream_1.0.orig.tar', 'upstream')
    >>> gbp.command_wrappers.Command('gzip', [ '-n', '%s/../upstream_1.0.orig.tar' % dirs['repo']])()
    >>> with open('%s/../upstream_1.0.orig.tar.gz.asc' % dirs['repo'], 'w') as f: f.write("sig")
    3
    >>> # test_pristine_tar_commit():
    >>> # Commit the delta to the pristine-tar branch
    >>> repo = gbp.deb.git.DebianGitRepository(dirs['repo'])
    >>> repo.pristine_tar.commit('../upstream_1.0.orig.tar.gz', 'upstream')
    >>> # test_pristine_tar_commit_with_sig():
    >>> # Commit the delta to the pristine-tar branch including a signature
    >>> repo = gbp.deb.git.DebianGitRepository(dirs['repo'])
    >>> repo.pristine_tar.commit('../upstream_1.0.orig.tar.gz', 'upstream',
    ...                          signaturefile='../upstream_1.0.orig.tar.gz.asc')
    >>> # test_pristine_has_commit():
    >>> # Find delta on the pristine tar branch
    >>> repo = gbp.deb.git.DebianGitRepository(dirs['repo'])
    >>> repo.pristine_tar.has_commit('upstream', '1.0', 'bzip2')
    False
    >>> repo.pristine_tar.has_commit('upstream', '1.0', 'gzip')
    True
    >>> repo.pristine_tar.has_commit('upstream', '1.0')
    True
    >>> branch = repo.rev_parse('pristine-tar')
    >>> commit, sig = repo.pristine_tar.get_commit('upstream_1.0.orig.tar.gz')
    >>> branch == commit
    True
    >>> sig
    True
    >>> repo.pristine_tar.commit('../upstream_1.0.orig.tar.gz', 'upstream')
    >>> branch = repo.rev_parse('pristine-tar')
    >>> commit, sig = repo.pristine_tar.get_commit('upstream_1.0.orig.tar.gz')
    >>> branch == commit
    True
    >>> sig
    False
    >>> # test_pristine_tar_checkout():
    >>> # Checkout a tarball using pristine-tar
    >>> repo = gbp.deb.git.DebianGitRepository(dirs['repo'])
    >>> repo.pristine_tar.checkout('upstream', '1.0', 'gzip', '..')
    >>> # test_pristine_tar_checkout_with_sig():
    >>> # Checkout a tarball using pristine-tar
    >>> from gbp.deb.policy import DebianPkgPolicy

    >>> repo = gbp.deb.git.DebianGitRepository(dirs['repo'])
    >>> sf = os.path.join(repo.path,
    ...                   DebianPkgPolicy.build_signature_name('upstream', '1.0', 'gzip', '..'))
    >>> os.unlink(sf)
    >>> repo.pristine_tar.checkout('upstream', '1.0', 'gzip', '..',
    ...                             signature=True)
    >>> os.path.exists(sf) or not repo.pristine_tar.has_feature_sig()
    True
    >>> # test_pristine_tar_verify():
    >>> # Verify a tarball using pristine-tar
    >>> repo = gbp.deb.git.DebianGitRepository(dirs['repo'])
    >>> if repo.pristine_tar.has_feature_verify():
    ...    repo.pristine_tar.verify('../upstream_1.0.orig.tar.gz')
    >>> # test_pristine_tar_checkout_nonexistent():
    >>> # Checkout a tarball that does not exist using pristine-tar
    >>> repo = gbp.deb.git.DebianGitRepository(dirs['repo'])
    >>> _gbp_log_err_bak = gbp.log.err
    >>> gbp.log.err = lambda x: None
    >>> repo.pristine_tar.checkout('upstream', '1.1', 'gzip', '..') # doctest:+IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    gbp.command_wrappers.CommandExecFailed: Pristine-tar couldn't checkout "upstream_1.1.orig.tar.gz": fatal: Path 'upstream_1.1.orig.tar.gz.delta' does not exist in 'refs/heads/pristine-tar'
    pristine-tar: git show refs/heads/pristine-tar:upstream_1.1.orig.tar.gz.delta failed
    >>> gbp.log.err = _gbp_log_err_bak
    >>> teardown_module()
    """

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
