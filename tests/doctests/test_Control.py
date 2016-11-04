# vim: set fileencoding=utf-8 :

"""
Test L{gbp.deb.control.Control}
"""

from .. import context  # noqa: 401

cl_debian = """Source: git-buildpackage
Section: vcs
Priority: optional
Maintainer: Guido Günther <agx@sigxcpu.org>
Build-Depends: debhelper (>= 7.0.50~), python (>> 2.6.6-3~),
 pychecker, gtk-doc-tools, sgml2x, docbook-utils, jade, python-dateutil, python-nose,
 bash-completion, perl, python-epydoc, python-coverage, python-setuptools,
 # For the testsuite
 git (>= 1:1.7.9.1-1~), bzip2, unzip, pristine-tar
Standards-Version: 3.9.3
Vcs-Git: git://honk.sigxcpu.org/git/git-buildpackage.git
Vcs-Browser: http://git.debian.org/?p=users/agx/git-buildpackage.git
Homepage: https://honk.sigxcpu.org/piki/projects/git-buildpackage/
X-Python-Version: >= 2.6

Package: git-buildpackage
Architecture: all
Depends: ${python:Depends}, ${shlibs:Depends}, ${misc:Depends}, devscripts (>= 2.10.66~),
 git (>= 1:1.7.9.1-1~), python-dateutil
Recommends: pristine-tar (>= 0.5), cowbuilder
Suggests: python-notify, unzip
Description: Suite to help with Debian packages in Git repositories
 This package contains the following tools:
  * git-import-{dsc,dscs}: import existing Debian source packages into a git
    repository
  * git-import-orig: import a new upstream version into the git repository
  * git-buildpackage: build a package out of a git repository, check for local
    modifications and tag appropriately
  * git-dch: generate Debian changelog entries from Git commit messages
  * gbp-{pull,clone}: clone and pull from remote repos
  * gbp-pq: manage debian/patches easily
  * gbp-create-remote-repo: create remote repositories
"""


def test_parse_control():
    """
    Parse a the control of debian package

    Methods tested:
         - L{gbp.deb.control.Control.__init__}

    Properties tested:
         - L{gbp.deb.control.Control.name}
         - L{gbp.deb.control.Control.section}
         - L{gbp.deb.control.Control.priority}

    >>> import gbp.deb.control
    >>> cl = gbp.deb.control.Control(cl_debian)
    >>> cl.name
    'git-buildpackage'
    >>> cl.name == cl['Source']
    True
    >>> cl.section
    'vcs'
    >>> cl.section == cl['Section']
    True
    >>> cl.priority
    'optional'
    >>> cl.priority == cl['Priority']
    True
    >>> cl['Standards-Version']
    '3.9.3'
    >>> cl['Package']

    """


def test_no_control_error():
    """
    Raise an error if no control file exist or is empty

    Methods tested:
         - L{gbp.deb.control.Control.__init__}

    >>> import gbp.deb.control
    >>> cl = gbp.deb.control.Control(filename="doesnotexist")
    Traceback (most recent call last):
    ...
    NoControlError: Control file doesnotexist does not exist
    >>> cl = gbp.deb.control.Control("notparsable")
    Traceback (most recent call last):
    ...
    ParseControlError: Empty or invalid control file or contents
    """
