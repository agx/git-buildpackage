# vim: set fileencoding=utf-8 :

"""
Test L{gbp.deb.changelog.ChangeLog}
"""
from .. import context  # noqa: 401
import os
import nose

cl_debian = """git-buildpackage (0.5.32) unstable; urgency=low

  * [efe9220] Use known_compressions in guess_upstream_version too
    (Closes: #645477)
  * [e984baf] git-import-orig: fix --filter

 -- Guido Günther <agx@sigxcpu.org>  Mon, 17 Oct 2011 10:15:22 +0200

git-buildpackage (0.5.31) unstable; urgency=low

  [ Guido Günther ]
  * [3588d88] Fix pristine-tar error message
  * [8da98da] gbp-pq: don't fail on missing series file but create an empty
    branch instead

  [ Salvatore Bonaccorso ]
  * [b33cf74] Fix URL to cl2vcs service.
    Refer to https://honk.sigxcpu.org/cl2vcs instead of
    https://honk.sigxcpu.org/cl2vcs for the cl2vcs service. (Closes: #640141)

 -- Guido Günther <agx@sigxcpu.org>  Wed, 28 Sep 2011 20:21:34 +0200
"""

cl_upstream = """python-dateutil (1.0-1) unstable; urgency=low

  * Initial release (Closes: #386256)

 -- Guido Günther <agx@sigxcpu.org>  Wed,  6 Sep 2006 10:33:06 +0200
"""

cl_epoch = """xserver-xorg-video-nv (1:1.2.0-3) unstable; urgency=low

  [ Steve Langasek ]
  * Upload to unstable

 -- David Nusinow <dnusinow@debian.org>  Mon, 18 Sep 2006 19:57:45 -0400
"""


def setup():
    """Setup test module"""
    if not os.path.exists('/usr/bin/debchange'):
        raise nose.SkipTest('debchange tool not present')


def test_parse_debian_only():
    """
    Parse a the changelog of debian only package

    Methods tested:
         - L{gbp.deb.changelog.ChangeLog.__init__}

    Properties tested:
         - L{gbp.deb.changelog.ChangeLog.version}
         - L{gbp.deb.changelog.ChangeLog.debian_version}
         - L{gbp.deb.changelog.ChangeLog.upstream_version}
         - L{gbp.deb.changelog.ChangeLog.epoch}
         - L{gbp.deb.changelog.ChangeLog.noepoch}

    >>> import gbp.deb.changelog
    >>> cl = gbp.deb.changelog.ChangeLog(cl_debian)
    >>> cl.version
    '0.5.32'
    >>> cl.version == cl['Version']
    True
    >>> cl.debian_version
    '0.5.32'
    >>> cl.debian_version == cl['Debian-Version']
    True
    >>> cl.noepoch
    '0.5.32'
    >>> cl.noepoch == cl['NoEpoch-Version']
    True
    >>> cl.epoch
    >>> cl.upstream_version
    """


def test_parse_no_eopch():
    """
    Parse a the changelog of a package without eopch

    Methods tested:
         - L{gbp.deb.changelog.ChangeLog.__init__}
         - L{gbp.deb.changelog.ChangeLog.has_epoch}

    Properties tested:
         - L{gbp.deb.changelog.ChangeLog.version}
         - L{gbp.deb.changelog.ChangeLog.debian_version}
         - L{gbp.deb.changelog.ChangeLog.upstream_version}
         - L{gbp.deb.changelog.ChangeLog.epoch}
         - L{gbp.deb.changelog.ChangeLog.noepoch}

    >>> import gbp.deb.changelog
    >>> cl = gbp.deb.changelog.ChangeLog(cl_upstream)
    >>> cl.version
    '1.0-1'
    >>> cl.version == cl['Version']
    True
    >>> cl.debian_version
    '1'
    >>> cl.debian_version == cl['Debian-Version']
    True
    >>> cl.noepoch
    '1.0-1'
    >>> cl.noepoch == cl['NoEpoch-Version']
    True
    >>> cl.epoch
    >>> cl.upstream_version
    '1.0'
    >>> cl.has_epoch()
    False
    """


def test_parse_eopch():
    """
    Parse a the changelog of a package without epoch

    Methods tested:
         - L{gbp.deb.changelog.ChangeLog.__init__}
         - L{gbp.deb.changelog.ChangeLog.has_epoch}

    Properties tested:
         - L{gbp.deb.changelog.ChangeLog.version}
         - L{gbp.deb.changelog.ChangeLog.debian_version}
         - L{gbp.deb.changelog.ChangeLog.upstream_version}
         - L{gbp.deb.changelog.ChangeLog.epoch}
         - L{gbp.deb.changelog.ChangeLog.noepoch}

    >>> import gbp.deb.changelog
    >>> cl = gbp.deb.changelog.ChangeLog(cl_epoch)
    >>> cl.version
    '1:1.2.0-3'
    >>> cl.version == cl['Version']
    True
    >>> cl.debian_version
    '3'
    >>> cl.debian_version == cl['Debian-Version']
    True
    >>> cl.noepoch
    '1.2.0-3'
    >>> cl.noepoch == cl['NoEpoch-Version']
    True
    >>> cl.epoch
    '1'
    >>> cl.upstream_version
    '1.2.0'
    >>> cl.has_epoch()
    True
    """


def test_parse_name():
    """
    Methods tested:
         - L{gbp.deb.changelog.ChangeLog.__init__}

    Properties tested:
         - L{gbp.deb.changelog.ChangeLog.name}

    >>> import gbp.deb.changelog
    >>> cl = gbp.deb.changelog.ChangeLog(cl_debian)
    >>> cl.name
    'git-buildpackage'
    """


def test_parse_last_mod():
    """
    Test author, email and date of last modification

    Methods tested:
         - L{gbp.deb.changelog.ChangeLog.__init__}

    Properties tested:
         - L{gbp.deb.changelog.ChangeLog.name}
         - L{gbp.deb.changelog.ChangeLog.email}
         - L{gbp.deb.changelog.ChangeLog.date}

    >>> import gbp.deb.changelog
    >>> cl = gbp.deb.changelog.ChangeLog(cl_debian)
    >>> cl.author.startswith('Guido')
    True
    >>> cl.email
    'agx@sigxcpu.org'
    >>> cl.date
    'Mon, 17 Oct 2011 10:15:22 +0200'
    """


def test_parse_sections():
    """
    Test if we can parse sections out of the changelog

    Methods tested:
         - L{gbp.deb.changelog.ChangeLog.__init__}
         - L{gbp.deb.changelog.ChangeLogSection.__init__}
         - L{gbp.deb.changelog.ChangeLogSection.parse}

    Properties tested:
         - L{gbp.deb.changelog.ChangeLog.sections}

    >>> import gbp.deb.changelog
    >>> cl = gbp.deb.changelog.ChangeLog(cl_debian)
    >>> cl.sections[0].package
    'git-buildpackage'
    >>> cl.sections[0].version
    '0.5.32'
    >>> cl.sections[1].package
    'git-buildpackage'
    >>> cl.sections[1].version
    '0.5.31'
    """


def test_add_section():
    """
    Test if we can add a section to an existing changelog

    Methods tested:
         - L{gbp.deb.changelog.ChangeLog.__init__}
         - L{gbp.deb.changelog.ChangeLog._parse}
         - L{gbp.deb.changelog.ChangeLog.add_section}
         - L{gbp.deb.changelog.ChangeLog.spawn_dch}

    >>> import os
    >>> import tempfile
    >>> import shutil
    >>> import gbp.deb.changelog
    >>> from ..testutils import OsReleaseFile
    >>> os_release = OsReleaseFile('/etc/lsb-release')
    >>> olddir = os.path.abspath(os.path.curdir)
    >>> testdir = tempfile.mkdtemp(prefix='gbp-test-changelog-')
    >>> testdebdir = os.path.join(testdir, 'debian')
    >>> testclname = os.path.join(testdebdir, "changelog")
    >>> os.mkdir(testdebdir)
    >>> clh = open(os.path.join(testdebdir, "changelog"), "w")
    >>> ret = clh.write(cl_debian)
    >>> clh.close()
    >>> os.chdir(testdir)
    >>> os.path.abspath(os.path.curdir) == testdir
    True
    >>> cl = gbp.deb.changelog.ChangeLog(filename=testclname)
    >>> cl.add_section(msg=["Test add section"], distribution=None, author="Debian Maintainer", email="maint@debian.org")
    >>> cl = gbp.deb.changelog.ChangeLog(filename=testclname)
    >>> version = '0.5.32ubuntu1' if os_release['DISTRIB_ID'] == 'Ubuntu' else '0.5.33'
    >>> cl.version == version
    True
    >>> cl.debian_version == version
    True
    >>> distributions = ['UNRELEASED', os_release['DISTRIB_CODENAME'] or 'unstable']
    >>> cl['Distribution'] in distributions
    True
    >>> 'Test add section' in cl['Changes']
    True
    >>> os.chdir(olddir)
    >>> os.path.abspath(os.path.curdir) == olddir
    True
    >>> shutil.rmtree(testdir, ignore_errors=True)
    """


def test_add_entry():
    """
    Test if we can add an entry to an existing changelog

    Methods tested:
         - L{gbp.deb.changelog.ChangeLog.__init__}
         - L{gbp.deb.changelog.ChangeLog._parse}
         - L{gbp.deb.changelog.ChangeLog.add_entry}
         - L{gbp.deb.changelog.ChangeLog.spawn_dch}

    >>> import os
    >>> import tempfile
    >>> import shutil
    >>> import gbp.deb.changelog
    >>> from ..testutils import OsReleaseFile
    >>> os_release = OsReleaseFile('/etc/lsb-release')
    >>> olddir = os.path.abspath(os.path.curdir)
    >>> testdir = tempfile.mkdtemp(prefix='gbp-test-changelog-')
    >>> testdebdir = os.path.join(testdir, 'debian')
    >>> testclname = os.path.join(testdebdir, "changelog")
    >>> os.mkdir(testdebdir)
    >>> clh = open(os.path.join(testdebdir, "changelog"), "w")
    >>> ret = clh.write(cl_debian)
    >>> clh.close()
    >>> os.chdir(testdir)
    >>> os.path.abspath(os.path.curdir) == testdir
    True
    >>> cl = gbp.deb.changelog.ChangeLog(filename=testclname)
    >>> cl.add_section(msg=["Test add section"], distribution=None, author="Debian Maintainer", email="maint@debian.org")
    >>> cl.add_entry(msg=["Test add entry"], author="Debian Maintainer", email="maint@debian.org")
    >>> cl = gbp.deb.changelog.ChangeLog(filename=testclname)
    >>> version = '0.5.32ubuntu1' if os_release['DISTRIB_ID'] == 'Ubuntu' else '0.5.33'
    >>> cl.version == version
    True
    >>> cl.debian_version == version
    True
    >>> distributions = ['UNRELEASED', os_release['DISTRIB_CODENAME'] or 'unstable']
    >>> cl['Distribution'] in distributions
    True
    >>> 'Test add entry' in cl['Changes']
    True
    >>> cl['Changes'].split('*',1)[1]
    ' Test add section\\n   * Test add entry'
    >>> os.chdir(olddir)
    >>> os.path.abspath(os.path.curdir) == olddir
    True
    >>> shutil.rmtree(testdir, ignore_errors=True)
    """
