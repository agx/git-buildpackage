# vim: set fileencoding=utf-8 :

"""
Test  L{gbp.deb.changelog.Changelog}

Test things here that don't fit nicely into the doctests that
also make up the API documentation.
"""

from . import context  # noqa: F401
from . testutils import skip_without_cmd
import os
import unittest

from gbp.deb.changelog import ChangeLog
from gbp.command_wrappers import CommandExecFailed


class TestQuoting(unittest.TestCase):
    def test_comma(self):
        """Test we properly parse maintainers with comma #737623"""
        changes = """git-buildpackage (0.9.2) unstable; urgency=low

  * List of changes

 -- Guido Günther, aftercomma <agx@sigxcpu.org>  Sun, 12 Nov 2017 19:00:00 +0200
"""
        cl = ChangeLog(changes)
        self.assertEquals(cl.author, 'Guido Günther, aftercomma')
        self.assertEquals(cl.email, 'agx@sigxcpu.org')


class TestEncoding(unittest.TestCase):
    def test_nul(self):
        """Test we remove NUL characters from strings when parsing (#981340)"""
        changes = """git-buildpackage (0.9.2) unstable; urgency=low

  * List of ch\0nges

 -- User N\0me <agx@sigxcpu.org>  Sun, 12 Nov 2017 19:00:00 +0200
"""
        cl = ChangeLog(changes)
        self.assertEquals(cl.author, 'User Nme')
        self.assertEquals(cl.email, 'agx@sigxcpu.org')
        self.assertEquals('\0' in cl.get_changes(), False)


@skip_without_cmd('debchange')
class Test(unittest.TestCase):
    def setUp(self):
        self.tmpdir = context.new_tmpdir(__name__)
        context.chdir(self.tmpdir)
        os.mkdir('debian/')

    def tearDown(self):
        context.teardown()

    def test_changelog_creation_full(self):
        cp = ChangeLog.create('package', '1.0')
        self.assertEquals(cp.name, 'package')
        self.assertEquals(cp.version, '1.0')

    def test_changelog_creation_version(self):
        cp = ChangeLog.create(version='1.0')
        self.assertEquals(cp.name, 'PACKAGE')
        self.assertEquals(cp.version, '1.0')

    def test_changelog_creation_package(self):
        cp = ChangeLog.create(package='package')
        self.assertEquals(cp.name, 'package')
        self.assertEquals(cp.version, 'unknown')

    def test_changelog_missing_dir(self):
        os.rmdir('debian/')
        with self.assertRaisesRegexp(CommandExecFailed, "Cannot find debian directory"):
            ChangeLog.create('package', '1.0')

    def test_changelog_exists(self):
        with open('debian/changelog', 'w') as f:
            f.write('')
        with self.assertRaisesRegexp(CommandExecFailed, "File debian/changelog already exists"):
            ChangeLog.create('package', '1.0')
