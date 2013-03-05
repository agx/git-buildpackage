# vim: set fileencoding=utf-8 :

"""
Test L{gbp.deb.changelog.ChangeLog}
"""

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

cl_upstream="""python-dateutil (1.0-1) unstable; urgency=low

  * Initial release (Closes: #386256)

 -- Guido Günther <agx@sigxcpu.org>  Wed,  6 Sep 2006 10:33:06 +0200
"""

cl_epoch="""xserver-xorg-video-nv (1:1.2.0-3) unstable; urgency=low

  [ Steve Langasek ]
  * Upload to unstable

 -- David Nusinow <dnusinow@debian.org>  Mon, 18 Sep 2006 19:57:45 -0400
"""

def setup():
    """Setup test module"""
    if not os.path.exists('/usr/bin/dch'):
        raise nose.SkipTest('dch tool not present')

def test_parse_debian_only():
    """
    Parse a the changelog of debian only package

    Methods tested:
         - L{gbp.deb.changelog.ChangeLog.__init__}
         - L{gbp.deb.changelog.ChangeLog.is_native}

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
    >>> cl.is_native()
    True
    """

def test_parse_no_eopch():
    """
    Parse a the changelog of a package without eopch

    Methods tested:
         - L{gbp.deb.changelog.ChangeLog.__init__}
         - L{gbp.deb.changelog.ChangeLog.has_epoch}
         - L{gbp.deb.changelog.ChangeLog.is_native}

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
    >>> cl.is_native()
    False
    """

def test_parse_eopch():
    """
    Parse a the changelog of a package without epoch

    Methods tested:
         - L{gbp.deb.changelog.ChangeLog.__init__}
         - L{gbp.deb.changelog.ChangeLog.has_epoch}
         - L{gbp.deb.changelog.ChangeLog.is_native}

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
    >>> cl.is_native()
    False
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
