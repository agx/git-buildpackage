# vim: set fileencoding=utf-8 :

"""Test L{gbp.deb}"""

from . import context  # noqa: 401

import os
import tempfile
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
 3743dc4f3e58d5912a98f568c3e854d97d81f123 20054618 libvirt_0.9.12.orig-foo.tar.gz
 3743dc4f3e58d5912a98f568c3e854d97d81f123 20054618 libvirt_0.9.12.orig-bar.tar.gz
 a7ffa64c18a5ee448c98b1dc894a0a27e1670357 35935 libvirt_0.9.12-4.debian.tar.gz
Checksums-Sha256:
 298ffc7f2a6d6e78aae46f11a0980f4bc17fa2928f5de6cd9e8abaf5990336e7 20054618 libvirt_0.9.12.orig.tar.gz
 298ffc7f2a6d6e78aae46f11a0980f4bc17fa2928f5de6cd9e8abaf599033123 20054618 libvirt_0.9.12.orig-foo.tar.gz
 298ffc7f2a6d6e78aae46f11a0980f4bc17fa2928f5de6cd9e8abaf599033123 20054618 libvirt_0.9.12.orig-bar.tar.gz
 e75110c493995ba5366e751f20f3842f30674c3918357fa6eb83175d0afbec31 35935 libvirt_0.9.12-4.debian.tar.gz
Files:
 5e842bc55733ceba60c64767580ff3e4 20054618 libvirt_0.9.12.orig.tar.gz
 5e842bc55733ceba60c64767580ff123 20054618 libvirt_0.9.12.orig-foo.tar.gz
 5e842bc55733ceba60c64767580ff123 20054618 libvirt_0.9.12.orig-bar.tar.gz
 f328960d25e7c843f3ac5f9ba5064251 35935 libvirt_0.9.12-4.debian.tar.gz
"""

    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False) as self.dscfile:
            self.dscfile.write(self.content)

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
        for s in ['foo', 'bar']:
            self.assertEqual(os.path.basename(dsc.additional_tarballs[s]),
                             'libvirt_0.9.12.orig-%s.tar.gz' % s)


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
            self.dscfile.write(self.content)

    def tearDown(self):
        os.unlink(self.dscfile.name)

    def test_dscfile_parse(self):
        """Test parsing a a 1.0 non-native dsc file without debian revision"""
        dsc = DscFile.parse(self.dscfile.name)
        self.assertEqual(dsc.version, '0.5')
        self.assertEqual(dsc.native, False)
        self.assertEqual(os.path.basename(dsc.tgz), 'latencytop_0.5.orig.tar.gz')
        self.assertEqual(os.path.basename(dsc.deb_tgz), '')
        self.assertEqual(os.path.basename(dsc.diff), 'latencytop_0.5.diff.gz')
        self.assertEqual(dsc.additional_tarballs, {}),


@unittest.skipIf(not os.path.exists('/usr/bin/dpkg'), 'Dpkg not found')
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
        self.assertRaises(CommandExecFailed, self.cmp, '_', '_ _')
