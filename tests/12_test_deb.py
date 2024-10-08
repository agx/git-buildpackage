# vim: set fileencoding=utf-8 :

"""Test L{gbp.deb}"""

from . import context  # noqa: F401
from . import testutils

import os
import tempfile
import platform
import unittest

import gbp.deb

from gbp.deb.dscfile import DscFile
from gbp.command_wrappers import CommandExecFailed


class Test30DscFile(unittest.TestCase):
    """Test L{gbp.deb.DscFile}"""

    content = """Format: 3.0 (quilt)
Source: libvirt
Binary: libvirt-bin, libvirt0, libvirt0-dbg, libvirt-doc, libvirt-dev, python-libvirt
Architecture: any all
Version: 0.9.12-4
Maintainer: Debian Libvirt Maintainers <pkg-libvirt-maintainers@lists.alioth.debian.org>
Uploaders: Guido Günther <agx@sigxcpu.org>, Laurent Léonard <laurent@open-minds.org>
Dm-Upload-Allowed: yes
Homepage: http://libvirt.org
Standards-Version: 3.9.3
Vcs-Browser: http://git.debian.org/?p=pkg-libvirt/libvirt.git
Vcs-Git: git://git.debian.org/git/pkg-libvirt/libvirt.git
Build-Depends: cdbs (>= 0.4.90~), debhelper (>= 7), libxml2-dev, libncurses5-dev, libreadline-dev, zlib1g-dev, libgcrypt11-dev, libgnutls-dev, python-all-dev (>= 2.6.6-3~), libavahi-client-dev, libsasl2-dev, libxen-dev [i386 amd64], lvm2 [linux-any], open-iscsi [linux-any], libparted0-dev (>= 2.2), parted (>= 2.2), libdevmapper-dev [linux-any], uuid-dev, libudev-dev [linux-any], libhal-dev [!linux-any], libpciaccess-dev, module-init-tools [linux-any], policykit-1, libcap-ng-dev [linux-any], libnl-dev [linux-any], libyajl-dev, libpcap0.8-dev, libnuma-dev [amd64 i386 ia64 mips mipsel powerpc], radvd [linux-any], libnetcf-dev [linux-any], dwarves, libxml2-utils, dnsmasq-base, openssh-client, netcat-openbsd
Build-Conflicts: dpkg-dev (= 1.15.3)
Package-List:
 libvirt-bin deb admin optional
 libvirt-dev deb libdevel optional
 libvirt-doc deb doc optional
 libvirt0 deb libs optional
 libvirt0-dbg deb debug extra
 python-libvirt deb python optional
Checksums-Sha1:
 3743dc4f3e58d5912a98f568c3e854d97d81f216 20054618 libvirt_0.9.12.orig.tar.gz
 7dc0f3bfe8a63a0259affe4fe3d3cc5b3180a72b 240 libvirt_0.9.12.orig.tar.gz.asc
 3743dc4f3e58d5912a98f568c3e854d97d81f123 20054618 libvirt_0.9.12.orig-foo.tar.gz
 7dc0f3bfe8a63a0259affe4fe3d3cc5b3180a72b 240 libvirt_0.9.12.orig-foo.tar.gz.asc
 3743dc4f3e58d5912a98f568c3e854d97d81f123 20054618 libvirt_0.9.12.orig-bar.tar.gz
 7dc0f3bfe8a63a0259affe4fe3d3cc5b3180a72b 240 libvirt_0.9.12.orig-bar.tar.gz.asc
 3743dc4f3e58d5912a98f568c3e854d97d81f12c 20054618 libvirt_0.9.12.orig-upper-CASE.tar.gz
 a7ffa64c18a5ee448c98b1dc894a0a27e1670357 35935 libvirt_0.9.12-4.debian.tar.gz
Checksums-Sha256:
 298ffc7f2a6d6e78aae46f11a0980f4bc17fa2928f5de6cd9e8abaf5990336e7 20054618 libvirt_0.9.12.orig.tar.gz
 2496f435c029673dd7cad49cdf27935d261ef1b3b245118a431556b7f40a7967 240 libvirt_0.9.12.orig.tar.gz.asc
 298ffc7f2a6d6e78aae46f11a0980f4bc17fa2928f5de6cd9e8abaf599033123 20054618 libvirt_0.9.12.orig-foo.tar.gz
 2496f435c029673dd7cad49cdf27935d261ef1b3b245118a431556b7f40a7967 240 libvirt_0.9.12.orig-foo.tar.gz.asc
 298ffc7f2a6d6e78aae46f11a0980f4bc17fa2928f5de6cd9e8abaf599033123 20054618 libvirt_0.9.12.orig-bar.tar.gz
 2496f435c029673dd7cad49cdf27935d261ef1b3b245118a431556b7f40a7967 240 libvirt_0.9.12.orig-bar.tar.gz.asc
 298ffc7f2a6d6e78aae46f11a0980f4bc17fa2928f5de6cd9e8abaf59903312c 20054618 libvirt_0.9.12.orig-upper-CASE.tar.gz
 e75110c493995ba5366e751f20f3842f30674c3918357fa6eb83175d0afbec31 35935 libvirt_0.9.12-4.debian.tar.gz
Files:
 5e842bc55733ceba60c64767580ff3e4 20054618 libvirt_0.9.12.orig.tar.gz
 ddfefbf64ffa1b1d7e0819501d096544 240 libvirt_0.9.12.orig.tar.gz.asc
 5e842bc55733ceba60c64767580ff123 20054618 libvirt_0.9.12.orig-foo.tar.gz
 ddfefbf64ffa1b1d7e0819501d096544 240 libvirt_0.9.12.orig-foo.tar.gz.asc
 5e842bc55733ceba60c64767580ff123 20054618 libvirt_0.9.12.orig-bar.tar.gz
 ddfefbf64ffa1b1d7e0819501d096544 240 libvirt_0.9.12.orig-bar.tar.gz.asc
 5e842bc55733ceba60c64767580ff12c 20054618 libvirt_0.9.12.orig-upper-CASE.tar.gz
 f328960d25e7c843f3ac5f9ba5064251 35935 libvirt_0.9.12-4.debian.tar.gz
"""

    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False) as self.dscfile:
            self.dscfile.write(self.content.encode())

    def tearDown(self):
        os.unlink(self.dscfile.name)

    def test_dscfile_parse(self):
        """Test parsing a valid dsc file"""
        dsc = DscFile.parse(self.dscfile.name)
        self.assertEqual(dsc.version, '0.9.12-4')
        self.assertEqual(dsc.native, False)
        self.assertEqual(os.path.basename(dsc.tgz), 'libvirt_0.9.12.orig.tar.gz')
        self.assertEqual(os.path.basename(dsc.diff), '')
        self.assertEqual(os.path.basename(dsc.deb_tgz), 'libvirt_0.9.12-4.debian.tar.gz')
        for s in ['foo', 'bar', 'upper-CASE']:
            self.assertEqual(os.path.basename(dsc.additional_tarballs[s]),
                             'libvirt_0.9.12.orig-%s.tar.gz' % s)
        self.assertEqual(sorted(dsc.sigs), ['/tmp/libvirt_0.9.12.orig-bar.tar.gz.asc',
                                            '/tmp/libvirt_0.9.12.orig-foo.tar.gz.asc',
                                            '/tmp/libvirt_0.9.12.orig.tar.gz.asc'])


class Test10DscNonNativeFile(unittest.TestCase):
    """Test L{gbp.deb.DscFile}"""

    content = """Format: 1.0
Source: latencytop
Binary: latencytop
Architecture: any
Version: 0.5
Maintainer: Giacomo Catenazzi <cate@debian.org>
Homepage: http://www.latencytop.org/
Standards-Version: 3.8.2
Build-Depends: cdbs, debhelper (>= 5), pkg-config, libncursesw5-dev, libglib2.0-dev, libgtk2.0-dev
Package-List:
 latencytop deb utils extra arch=any
Checksums-Sha1:
 cfd8a83fa40e630cf680d96a186ff4fdbf6f22c8 25374 latencytop_0.5.orig.tar.gz
 1fa907254c61c73679fd173c828327e9a2273c31 1978 latencytop_0.5.diff.gz
Checksums-Sha256:
 9e7f72fbea7bd918e71212a1eabaad8488d2c602205d2e3c95d62cd57e9203ef 25374 latencytop_0.5.orig.tar.gz
 66342c4d55ae31e529bdcdf88d41a7d114b355f438b0d10efb107f3aef1a0db6 1978 latencytop_0.5.diff.gz
Files:
 73bb3371c6ee0b0e68e25289027e865c 25374 latencytop_0.5.orig.tar.gz
 bf7afb3e0d68b0e33e5abf4f1542af71 1978 latencytop_0.5.diff.gz
"""

    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False) as self.dscfile:
            self.dscfile.write(self.content.encode())

    def tearDown(self):
        os.unlink(self.dscfile.name)

    def test_dscfile_parse(self):
        """Test parsing a 1.0 non-native dsc file without debian revision"""
        dsc = DscFile.parse(self.dscfile.name)
        self.assertEqual(dsc.version, '0.5')
        self.assertEqual(dsc.native, False)
        self.assertEqual(os.path.basename(dsc.tgz), 'latencytop_0.5.orig.tar.gz')
        self.assertEqual(os.path.basename(dsc.deb_tgz), '')
        self.assertEqual(os.path.basename(dsc.diff), 'latencytop_0.5.diff.gz')
        self.assertEqual(dsc.additional_tarballs, {}),
        self.assertEqual(dsc.sigs, [])


class Test10DscNativeFileWithDebianRevision(unittest.TestCase):
    """Test L{gbp.deb.DscFile} with version string containing a Debian revision part"""

    content = """Format: 1.0
Source: python3-defaults
Binary: python3, python3-venv, python3-minimal, python3-nopie, python3-examples, python3-dev, libpython
3-dev, libpython3-stdlib, idle, python3-doc, python3-dbg, libpython3-dbg, python3-all, python3-all-dev,
 python3-all-dbg, python3-all-venv, libpython3-all-dev, libpython3-all-dbg, 2to3, python3-full
Architecture: any all
Version: 3.12.4-1
Maintainer: Matthias Klose <doko@debian.org>
Uploaders: Piotr Ożarowski <piotr@debian.org>, Stefano Rivera <stefanor@debian.org>
Homepage: https://www.python.org/
Standards-Version: 4.6.2
Vcs-Browser: https://salsa.debian.org/cpython-team/python3-defaults
Vcs-Git: https://salsa.debian.org/cpython-team/python3-defaults.git
Build-Depends: debhelper (>= 11), dpkg-dev (>= 1.17.11), python3.12:any (>= 3.12.4-1~), python3.12-minimal:any, python3-docutils <!nodoc>, python3-sphinx <!nodoc>, html2text (>= 2) <!nodoc>
Package-List:
 2to3 deb python optional arch=all
 idle deb python optional arch=all
 libpython3-all-dbg deb debug optional arch=any
 libpython3-all-dev deb libdevel optional arch=any
 libpython3-dbg deb debug optional arch=any
 libpython3-dev deb libdevel optional arch=any
 libpython3-stdlib deb python optional arch=any
 python3 deb python optional arch=any
 python3-all deb python optional arch=any
 python3-all-dbg deb debug optional arch=any
 python3-all-dev deb python optional arch=any
 python3-all-venv deb python optional arch=any
 python3-dbg deb debug optional arch=any
 python3-dev deb python optional arch=any
 python3-doc deb doc optional arch=all
 python3-examples deb python optional arch=all
 python3-full deb python optional arch=any
 python3-minimal deb python optional arch=any
 python3-nopie deb python optional arch=any
 python3-venv deb python optional arch=any
Checksums-Sha1:
 2eed084fb55c6f903413b0c9cc876e2e31197133 146851 python3-defaults_3.12.4-1.tar.gz
Checksums-Sha256:
 5ed419073282df22cddeb50a44b36f5607104d52999b93525dcd3970ea9a478f 146851 python3-defaults_3.12.4-1.tar.gz
"""

    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False) as self.dscfile:
            self.dscfile.write(self.content.encode())

    def tearDown(self):
        os.unlink(self.dscfile.name)

    def test_dscfile_parse(self):
        """Test parsing a 1.0 native dsc file with debian revision"""
        dsc = DscFile.parse(self.dscfile.name)
        self.assertEqual(dsc.version, '3.12.4-1')
        self.assertEqual(dsc.native, True)
        self.assertEqual(os.path.basename(dsc.tgz), 'python3-defaults_3.12.4-1.tar.gz')
        self.assertEqual(os.path.basename(dsc.deb_tgz), '')
        self.assertEqual(os.path.basename(dsc.diff), '')
        self.assertEqual(dsc.additional_tarballs, {}),
        self.assertEqual(dsc.sigs, [])


class Test30DscFileNonUtf8(unittest.TestCase):
    """Test L{gbp.deb.DscFile} with non-UTF8 dsc"""

    content = """Format: 3.0 (quilt)
Source: libvirt
Uploaders: Guido Günther <agx@sigxcpu.org>, Laurent Léonard <laurent@open-minds.org>
"""

    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False) as self.dscfile:
            self.dscfile.write(self.content.encode('iso8859-1'))

    def tearDown(self):
        os.unlink(self.dscfile.name)

    def test_dscfile_parse(self):
        """Test parsing an invalid (non-UTF8) dsc file"""
        with self.assertRaisesRegex(gbp.errors.GbpError, "is not UTF-8 encoded"):
            DscFile.parse(self.dscfile.name)


@testutils.skip_without_cmd('dpkg')
class TestDpkgCompareVersions(unittest.TestCase):
    """Test L{gbp.deb.DpkgCompareVersions}"""

    def setUp(self):
        self.cmp = gbp.deb.DpkgCompareVersions()

    def testLessThen(self):
        ret = self.cmp('1', '2')
        self.assertEqual(ret, -1)

    def testGreaterThen(self):
        ret = self.cmp('2', '1')
        self.assertEqual(ret, 1)

    def testSameVersion(self):
        ret = self.cmp('2', '2')
        self.assertEqual(ret, 0)

    def testBadVersion(self):
        with self.assertRaises(CommandExecFailed):
            self.cmp('_', '_ _')


@testutils.skip_without_cmd('dpkg')
class TestDeb(unittest.TestCase):
    """Test L{gbp.deb.__init__} """

    @unittest.skipUnless(platform.machine() == "x86_64" and platform.architecture()[0] == '64bit', "not on amd64")
    def test_get_arch(self):
        arch = gbp.deb.get_arch()
        self.assertTrue(isinstance(arch, str))
        self.assertEqual(arch, "amd64")

    @unittest.skipUnless(testutils.OsReleaseFile()['ID'] == 'debian', "not on Debian")
    def test_get_vendor(self):
        vendor = gbp.deb.get_vendor()
        self.assertTrue(isinstance(vendor, str))
        self.assertEqual(vendor, "Debian")
