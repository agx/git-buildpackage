# vim: set fileencoding=utf-8 :

"""Test L{gbp.scripts.dch} main"""

import unittest

from tests.testutils import DebianGitTestRepo

from gbp.scripts import dch

import os
import re

# Snapshot of version 0.9-2~1
snap_header_0_9 = r'^test-package\s\(0.9-2~1\.gbp([0-9a-f]{6})\)\sUNRELEASED;\surgency=low'
# Snapshot of version 1.0-1~1
snap_header_1 = r'^test-package\s\(1.0-1~1\.gbp([0-9a-f]{6})\)\sUNRELEASED;\surgency=low'
# Snapshot of version 1.0-1~2
snap_header_1_2 = r'^test-package\s\(1.0-1~2\.gbp([0-9a-f]{6})\)\sUNRELEASED;\surgency=low'

snap_mark = r'\s{2}\*{2}\sSNAPSHOT\sbuild\s@'

cl_debian = """test-package (0.9-1) unstable; urgency=low

  [ Debian Maintainer ]
  * New pre stable upstream release

 -- Debian Maintainer <maint@debian.org>  Mon, 17 Oct 2011 10:15:22 +0200
"""

@unittest.skipIf(not os.path.exists('/usr/bin/dch'), "Dch not found")
class TestScriptDch(DebianGitTestRepo):
    """Test git-dch"""

    def setUp(self):
        DebianGitTestRepo.setUp(self)
        self.add_file("foo", "bar")
        self.repo.create_tag("upstream/0.9", msg="upstream version 0.9")
        self.add_file("bar", "foo")
        self.repo.create_tag("upstream/1.0", msg="upstream version 1.0")
        self.repo.create_branch("debian")
        self.repo.set_branch("debian")
        self.upstream_tag = "upstream/%(version)s"
        self.top = os.path.abspath(os.path.curdir)
        os.mkdir(os.path.join(self.repo.path, "debian"))
        os.chdir(self.repo.path)
        self.add_file("debian/changelog", cl_debian)
        self.add_file("debian/control", """Source: test-package\nSection: test\n""")
        self.options = ["--upstream-tag=%s" % self.upstream_tag, "--debian-branch=debian",
                        "--id-length=0", "--spawn-editor=/bin/true"]

    def tearDown(self):
        os.chdir(self.top)
        DebianGitTestRepo.tearDown(self)

    def test_dch_main_new_upstream_version(self):
        """Test dch.py like git-dch script does: new upstream version"""
        options = self.options[:]
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        self.assertEqual("test-package (1.0-1) UNRELEASED; urgency=low\n", lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_release(self):
        """Test dch.py like git-dch script does: new upstream version - release"""
        options = self.options[:]
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        options.append("--release")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        self.assertEqual("test-package (1.0-1) unstable; urgency=low\n", lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_auto(self):
        """Test dch.py like git-dch script does: new upstream version - guess last commit"""
        options = self.options[:]
        options.append("--auto")
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        self.assertEqual("test-package (1.0-1) UNRELEASED; urgency=low\n", lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_snapshot(self):
        """Test dch.py like git-dch script does: new upstream version - snashot mode"""
        options = self.options[:]
        options.append("--snapshot")
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        header = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header)
        self.assertEqual(header.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_2_snapshots_auto(self):
        """Test dch.py like git-dch script does: new upstream version - two snapshots - auto"""
        options = self.options[:]
        options.append("--snapshot")
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        header1 = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header1)
        self.assertEqual(header1.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header1.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)
        # New snapshot, use auto to guess last one
        options.append("--auto")
        self.add_file("debian/compat", "9")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        header2 = re.search(snap_header_1_2, lines[0])
        self.assertIsNotNone(header2)
        self.assertEqual(header2.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header2.group(1), lines[2]))
        # First snapshot entry must be concatenated with the last one
        self.assertNotIn(header1.group(0) + "\n", lines)
        self.assertIn("""  * added debian/control\n""", lines)
        self.assertIn("""  * added debian/compat\n""", lines)

    def test_dch_main_new_upstream_version_with_2_snapshots_commit_auto(self):
        """Test dch.py like git-dch script does: new upstream version - two committed snapshots - auto"""
        options = self.options[:]
        options.append("--commit")
        options.append("--commit-msg=TEST-COMMITTED-SNAPSHOT")
        options.append("--snapshot")
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        header1 = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header1)
        self.assertEqual(header1.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header1.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)
        # New snapshot, use auto to guess last one
        options.append("--auto")
        self.add_file("debian/compat", "9")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        header2 = re.search(snap_header_1_2, lines[0])
        self.assertIsNotNone(header2)
        self.assertEqual(header2.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header2.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)
        self.assertIn("""  * added debian/compat\n""", lines)
        # First snapshot entry must have disapear
        self.assertNotIn(header1.group(0) + "\n", lines)
        # But its changelog must be included in the new one
        self.assertIn("""  * TEST-COMMITTED-SNAPSHOT\n""", lines)

    def test_dch_main_new_upstream_version_with_auto_release(self):
        """Test dch.py like git-dch script does: new upstream version - auto - release"""
        options = self.options[:]
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        options.append("--auto")
        options.append("--release")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        self.assertEqual("test-package (1.0-1) unstable; urgency=low\n", lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_auto_snapshot(self):
        """Test dch.py like git-dch script does: new upstream version - auto - snashot mode"""
        options = self.options[:]
        options.append("--auto")
        options.append("--snapshot")
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        header = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header)
        self.assertEqual(header.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_snapshot_release(self):
        """Test dch.py like git-dch script does: new upstream version - snashot - release"""
        options = self.options[:]
        options.append("--snapshot")
        options.append("--release")
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        self.assertRaises(SystemExit, dch.main, options)

    def test_dch_main_increment_debian_version(self):
        """Test dch.py like git-dch script does: increment debian version"""
        options = self.options[:]
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~2")
        self.repo.delete_tag("upstream/1.0")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        self.assertEqual("test-package (0.9-2) UNRELEASED; urgency=low\n", lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_increment_debian_version_with_release(self):
        """Test dch.py like git-dch script does: increment debian version - release"""
        options = self.options[:]
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        self.repo.delete_tag("upstream/1.0")
        options.append("--release")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        self.assertEqual("test-package (0.9-2) unstable; urgency=low\n", lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_increment_debian_version_with_auto(self):
        """Test dch.py like git-dch script does: increment debian version - guess last commit"""
        options = self.options[:]
        options.append("--auto")
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        self.repo.delete_tag("upstream/1.0")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        self.assertEqual("test-package (0.9-2) UNRELEASED; urgency=low\n", lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_increment_debian_version_with_snapshot(self):
        """Test dch.py like git-dch script does: increment debian version - snashot mode"""
        options = self.options[:]
        options.append("--snapshot")
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        self.repo.delete_tag("upstream/1.0")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        header = re.search(snap_header_0_9, lines[0])
        self.assertIsNotNone(header)
        self.assertEqual(header.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_increment_debian_version_with_auto_release(self):
        """Test dch.py like git-dch script does: increment debian version - auto - release"""
        options = self.options[:]
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        self.repo.delete_tag("upstream/1.0")
        options.append("--auto")
        options.append("--release")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        self.assertEqual("test-package (0.9-2) unstable; urgency=low\n", lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_increment_debian_version_with_auto_snapshot(self):
        """Test dch.py like git-dch script does: increment debian version - auto - snashot mode"""
        options = self.options[:]
        options.append("--auto")
        options.append("--snapshot")
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~1")
        self.repo.delete_tag("upstream/1.0")
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        lines = file("debian/changelog").readlines()
        header = re.search(snap_header_0_9, lines[0])
        self.assertIsNotNone(header)
        self.assertEqual(header.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)
