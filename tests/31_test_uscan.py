# vim: set fileencoding=utf-8 :

"""Test L{gbp.deb}"""

from . import context  # noqa: 401
from . import testutils

import unittest

from gbp.deb.uscan import Uscan


class TestUscan(unittest.TestCase):
    """Test L{gbp.deb.uscan}"""

    uscan_ok = b"""<dehs>
uscan: Newest version of virt-what on remote site is 1.18, local version is 1.15
uscan:    => Newer package available from
      https://people.redhat.com/~rjones/virt-what/files/virt-what-1.18.tar.gz
gpgv: Signature made Mo 31 Jul 2017 11:36:08 ADT
gpgv:                using RSA key 91738F73E1B768A0
gpgv: Good signature from "Richard W.M. Jones <rjones@redhat.com>"
gpgv:                 aka "Richard W.M. Jones <rich@annexia.org>"
<package>virt-what</package>
<debian-uversion>1.15</debian-uversion>
<debian-mangled-uversion>1.15</debian-mangled-uversion>
<upstream-version>1.18</upstream-version>
<upstream-url>https://people.redhat.com/~rjones/virt-what/files/virt-what-1.18.tar.gz</upstream-url>
<status>newer package available</status>
<target>virt-what_1.18.orig.tar.gz</target>
<target-path>../virt-what_1.18.orig.tar.gz</target-path>
<messages>Not downloading, using existing file: virt-what-1.18.tar.gz
</messages>
<messages>Leaving ../virt-what_1.18.orig.tar.gz where it is.
</messages>
</dehs>"""

    @testutils.patch_popen(stdout=uscan_ok, stderr=b'', returncode=0)
    def test_uscan(self, uscan_mock):
        """Test parsing a valid uscan file"""
        uscan = Uscan()
        self.assertTrue(uscan.scan())
        self.assertFalse(uscan.uptodate)
        self.assertEquals(uscan.tarball, '../virt-what_1.18.orig.tar.gz')
