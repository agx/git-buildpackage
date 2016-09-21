# vim: set fileencoding=utf-8 :

"""Test L{gbp.scripts.dch} main"""

from . import context
from .testutils import (DebianGitTestRepo, OsReleaseFile,
                        get_dch_default_urgency, capture_stderr)

from gbp.scripts import dch

import unittest
import os
import re

# Older dch compatibility
default_urgency = get_dch_default_urgency()

# For Ubuntu compatibility
os_release = OsReleaseFile('/etc/lsb-release')

# OS release codename and snapshot of version 0.9-2~1
if os_release['DISTRIB_ID'] == 'Ubuntu':
    os_codename = os_release['DISTRIB_CODENAME']
    snap_header_0_9 = r'^test-package\s\(0.9-1ubuntu1~1\.gbp([0-9a-f]{6})\)\sUNRELEASED;\surgency=%s' % default_urgency
    new_version_0_9 = '0.9-1ubuntu1'
else:
    os_codename = 'unstable'
    snap_header_0_9 = r'^test-package\s\(0.9-2~1\.gbp([0-9a-f]{6})\)\sUNRELEASED;\surgency=%s' % default_urgency
    new_version_0_9 = '0.9-2'
# Snapshot of version 1.0-1~1
snap_header_1 = r'^test-package\s\(1.0-1~1\.gbp([0-9a-f]{6})\)\sUNRELEASED;\surgency=%s' % default_urgency
# Snapshot of version 1.0-1~2
snap_header_1_2 = r'^test-package\s\(1.0-1~2\.gbp([0-9a-f]{6})\)\sUNRELEASED;\surgency=%s' % default_urgency

snap_mark = r'\s{2}\*{2}\sSNAPSHOT\sbuild\s@'

deb_tag = "debian/0.9-1"
deb_tag_msg = "Pre stable release version 0.9-1"

cl_debian = """test-package (0.9-1) unstable; urgency=%s

  [ Debian Maintainer ]
  * New pre stable upstream release

 -- Debian Maintainer <maint@debian.org>  Mon, 17 Oct 2011 10:15:22 +0200
""" % default_urgency


@unittest.skipIf(not os.path.exists('/usr/bin/debchange'), "Dch not found")
class TestScriptDch(DebianGitTestRepo):
    """Test git-dch"""

    def setUp(self):
        DebianGitTestRepo.setUp(self)
        self.add_file("foo", "bar")
        self.repo.create_tag("upstream/0.9", msg="upstream version 0.9")
        self.add_file("bar", "foo")
        self.repo.create_tag("upstream/1.0", msg="upstream version 1.0")
        self.repo.create_branch("upstream")
        self.repo.create_branch("debian")
        self.repo.set_branch("debian")
        self.upstream_tag = "upstream/%(version)s"
        self.top = os.path.abspath(os.path.curdir)
        os.mkdir(os.path.join(self.repo.path, "debian"))
        context.chdir(self.repo.path)
        self.add_file("debian/changelog", cl_debian)
        self.add_file("debian/control", """Source: test-package\nSection: test\n""")
        self.options = ["--upstream-tag=%s" % self.upstream_tag, "--debian-branch=debian",
                        "--upstream-branch=upstream", "--id-length=0", "--spawn-editor=/bin/true"]
        self.repo.create_tag(deb_tag, msg=deb_tag_msg, commit="HEAD~1")

    def tearDown(self):
        DebianGitTestRepo.tearDown(self)

    def run_dch(self, dch_options=None):
        # Take care to copy the list
        options = self.options[:]
        if dch_options is not None:
            options.extend(dch_options)
        ret = dch.main(options)
        self.assertEqual(ret, 0)
        return open("debian/changelog").readlines()

    def test_dch_main_new_upstream_version(self):
        """Test dch.py like gbp dch script does: new upstream version"""
        lines = self.run_dch()
        self.assertEqual("test-package (1.0-1) UNRELEASED; urgency=%s\n" % default_urgency, lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_release(self):
        """Test dch.py like gbp dch script does: new upstream version - release"""
        options = ["--release"]
        lines = self.run_dch(options)
        self.assertEqual("test-package (1.0-1) %s; urgency=%s\n" % (os_codename, default_urgency), lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_auto(self):
        """Test dch.py like gbp dch script does: new upstream version - guess last commit"""
        options = ["--auto"]
        lines = self.run_dch(options)
        self.assertEqual("test-package (1.0-1) UNRELEASED; urgency=%s\n" % default_urgency, lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_snapshot(self):
        """Test dch.py like gbp dch script does: new upstream version - snapshot mode"""
        options = ["--snapshot"]
        lines = self.run_dch(options)
        header = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header)
        self.assertEqual(header.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_2_snapshots_auto(self):
        """Test dch.py like gbp dch script does: new upstream version - two snapshots - auto"""
        options = ["--snapshot"]
        lines = self.run_dch(options)
        header1 = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header1)
        self.assertEqual(header1.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header1.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)
        # New snapshot, use auto to guess last one
        self.add_file("debian/compat", "9")
        options.append("--auto")
        lines = self.run_dch(options)
        header2 = re.search(snap_header_1_2, lines[0])
        self.assertIsNotNone(header2)
        self.assertEqual(header2.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header2.group(1), lines[2]))
        # First snapshot entry must be concatenated with the last one
        self.assertNotIn(header1.group(0) + "\n", lines)
        self.assertIn("""  * added debian/control\n""", lines)
        self.assertIn("""  * added debian/compat\n""", lines)

    def test_dch_main_new_upstream_version_with_2_snapshots_commit_auto(self):
        """Test dch.py like gbp dch script does: new upstream version - two committed snapshots - auto"""
        options = ["--commit"]
        options.append("--commit-msg=TEST-COMMITTED-SNAPSHOT")
        options.append("--snapshot")
        lines = self.run_dch(options)
        header1 = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header1)
        self.assertEqual(header1.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header1.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)
        # New snapshot, use auto to guess last one
        self.add_file("debian/compat", "9")
        options.append("--auto")
        lines = self.run_dch(options)
        header2 = re.search(snap_header_1_2, lines[0])
        self.assertIsNotNone(header2)
        self.assertEqual(header2.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header2.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)
        self.assertIn("""  * added debian/compat\n""", lines)
        # First snapshot entry must have disappeared
        self.assertNotIn(header1.group(0) + "\n", lines)
        # But its changelog must be included in the new one
        self.assertIn("""  * TEST-COMMITTED-SNAPSHOT\n""", lines)

    def test_dch_main_new_upstream_version_with_auto_release(self):
        """Test dch.py like gbp dch script does: new upstream version - auto - release"""
        options = ["--auto", "--release"]
        lines = self.run_dch(options)
        self.assertEqual("test-package (1.0-1) %s; urgency=%s\n" % (os_codename, default_urgency), lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_auto_snapshot(self):
        """Test dch.py like gbp dch script does: new upstream version - auto - snapshot mode"""
        options = ["--auto", "--snapshot"]
        options.append("--snapshot")
        lines = self.run_dch(options)
        header = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header)
        self.assertEqual(header.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_snapshot_release(self):
        """Test dch.py like gbp dch script does: new upstream version - snapshot - release"""
        options = ["--snapshot", "--release"]
        with capture_stderr() as c:
            self.assertRaises(SystemExit, self.run_dch, options)
        self.assertTrue("'--snapshot' and '--release' are incompatible options" in c.output())

    def test_dch_main_new_upstream_version_with_distribution(self):
        """Test dch.py like gbp dch script does: new upstream version - set distribution"""
        options = ["--distribution=testing", "--force-distribution"]
        lines = self.run_dch(options)
        self.assertEqual("test-package (1.0-1) testing; urgency=%s\n" % default_urgency, lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_release_distribution(self):
        """Test dch.py like gbp dch script does: new upstream version - release - set distribution"""
        options = ["--release", "--distribution=testing", "--force-distribution"]
        lines = self.run_dch(options)
        self.assertEqual("test-package (1.0-1) testing; urgency=%s\n" % default_urgency, lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_snapshot_distribution(self):
        """Test dch.py like gbp dch script does: new upstream version - snapshot mode - do not set distribution"""
        options = ["--snapshot", "--distribution=testing"]
        lines = self.run_dch(options)
        header = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header)
        self.assertEqual(header.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_2_snapshots_auto_distribution(self):
        """Test dch.py like gbp dch script does: new upstream version - two snapshots - do not set distribution"""
        options = ["--snapshot", "--distribution=testing"]
        lines = self.run_dch(options)
        header1 = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header1)
        self.assertEqual(header1.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header1.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)
        # New snapshot, use auto to guess last one
        self.add_file("debian/compat", "9")
        options.append("--auto")
        lines = self.run_dch(options)
        header2 = re.search(snap_header_1_2, lines[0])
        self.assertIsNotNone(header2)
        self.assertEqual(header2.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header2.group(1), lines[2]))
        # First snapshot entry must be concatenated with the last one
        self.assertNotIn(header1.group(0) + "\n", lines)
        self.assertIn("""  * added debian/control\n""", lines)
        self.assertIn("""  * added debian/compat\n""", lines)
        # But its changelog must not be included in the new one since
        # we do not commit
        self.assertNotIn("""  * TEST-COMMITTED-SNAPSHOT\n""", lines)

    def test_dch_main_new_upstream_version_with_2_snapshots_commit_auto_distribution(self):
        """Test dch.py like gbp dch script does: new upstream version - two committed snapshots - do not set distribution"""
        options = ["--commit"]
        options.append("--commit-msg=TEST-COMMITTED-SNAPSHOT")
        options.append("--snapshot")
        options.append("--distribution=testing")
        lines = self.run_dch(options)
        header1 = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header1)
        self.assertEqual(header1.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header1.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)
        # New snapshot, use auto to guess last one
        self.add_file("debian/compat", "9")
        options.append("--auto")
        lines = self.run_dch(options)
        header2 = re.search(snap_header_1_2, lines[0])
        self.assertIsNotNone(header2)
        self.assertEqual(header2.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header2.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)
        self.assertIn("""  * added debian/compat\n""", lines)
        # First snapshot entry must have disappeared
        self.assertNotIn(header1.group(0) + "\n", lines)
        # But its changelog must be included in the new one
        self.assertIn("""  * TEST-COMMITTED-SNAPSHOT\n""", lines)

    def test_dch_main_new_upstream_version_with_urgency(self):
        """Test dch.py like gbp dch script does: new upstream version - set urgency"""
        options = ["--urgency=emergency"]
        lines = self.run_dch(options)
        self.assertEqual("test-package (1.0-1) UNRELEASED; urgency=emergency\n", lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_release_urgency(self):
        """Test dch.py like gbp dch script does: new upstream version - release - set urgency"""
        options = ["--release", "--urgency=emergency"]
        lines = self.run_dch(options)
        self.assertEqual("test-package (1.0-1) %s; urgency=emergency\n" % os_codename, lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_new_upstream_version_with_snapshot_urgency(self):
        """Test dch.py like gbp dch script does: new upstream version - snapshot mode - set urgency"""
        options = ["--snapshot", "--urgency=emergency"]
        lines = self.run_dch(options)
        header = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header)
        self.assertEqual(header.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_increment_debian_version(self):
        """Test dch.py like gbp dch script does: increment debian version"""
        self.repo.delete_tag("debian/0.9-1")
        self.repo.create_tag("debian/0.9-1", msg="Pre stable release version 0.9-1", commit="HEAD~2")
        self.repo.delete_tag("upstream/1.0")
        lines = self.run_dch()
        self.assertEqual("test-package (%s) UNRELEASED; urgency=%s\n" % (new_version_0_9, default_urgency), lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_increment_debian_version_with_release(self):
        """Test dch.py like gbp dch script does: increment debian version - release"""
        self.repo.delete_tag("upstream/1.0")
        options = ["--release"]
        lines = self.run_dch(options)
        self.assertEqual("test-package (%s) %s; urgency=%s\n" % (new_version_0_9, os_codename, default_urgency), lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_increment_debian_version_with_auto(self):
        """Test dch.py like gbp dch script does: increment debian version - guess last commit"""
        self.repo.delete_tag("upstream/1.0")
        options = ["--auto"]
        lines = self.run_dch(options)
        self.assertEqual("test-package (%s) UNRELEASED; urgency=%s\n" % (new_version_0_9, default_urgency), lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_increment_debian_version_with_snapshot(self):
        """Test dch.py like gbp dch script does: increment debian version - snapshot mode"""
        self.repo.delete_tag("upstream/1.0")
        options = ["--snapshot"]
        lines = self.run_dch(options)
        header = re.search(snap_header_0_9, lines[0])
        self.assertIsNotNone(header)
        self.assertEqual(header.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_increment_debian_version_with_auto_release(self):
        """Test dch.py like gbp dch script does: increment debian version - auto - release"""
        self.repo.delete_tag("upstream/1.0")
        options = ["--auto", "--release"]
        lines = self.run_dch(options)
        self.assertEqual("test-package (%s) %s; urgency=%s\n" % (new_version_0_9, os_codename, default_urgency), lines[0])
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_increment_debian_version_with_auto_snapshot(self):
        """Test dch.py like gbp dch script does: increment debian version - auto - snapshot mode"""
        self.repo.delete_tag("upstream/1.0")
        options = ["--auto", "--snapshot"]
        lines = self.run_dch(options)
        header = re.search(snap_header_0_9, lines[0])
        self.assertIsNotNone(header)
        self.assertEqual(header.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_unreleased_debian_version_with_snapshot(self):
        """Test dch.py like gbp dch script does: snapshot mode with unreleased debian version"""
        new_version_1_0 = '1.0-1'
        options = ["--commit"]
        options.append("--commit-msg=UNRELEASED-version")
        lines = self.run_dch()
        header = re.search(r"\(%s\) UNRELEASED" % new_version_1_0, lines[0])
        self.assertIsNotNone(header)
        options = ["--snapshot", "--auto"]
        lines = self.run_dch(options)
        header = re.search(snap_header_1, lines[0])
        self.assertIsNotNone(header)
        self.assertEqual(header.lastindex, 1)
        self.assertIsNotNone(re.search(snap_mark + header.group(1), lines[2]))
        self.assertIn("""  * added debian/control\n""", lines)

    def test_dch_main_closes_default(self):
        options = ["--meta"]
        self.add_file("closes", "test file",
                      msg="""test debian closes commit\n\nCloses: #123456""")
        lines = self.run_dch(options)
        self.assertIn("""  * test debian closes commit (Closes: #123456)\n""",
                      lines)

    def test_dch_main_closes_non_debian_bug_numbers(self):
        self.add_file("closes", "test file",
                      msg="""test non-debian closes 1\n\nCloses: EX-123""")
        self.add_file("closes1", "test file",
                      msg="""test non-debian closes 2\n\nCloses: EX-5678""")
        options = ["--meta", '--meta-closes-bugnum=ex-\d+']
        lines = self.run_dch(options)
        self.assertIn("""  * test non-debian closes 1 (Closes: EX-123)\n""",
                      lines)
        self.assertIn("""  * test non-debian closes 2 (Closes: EX-5678)\n""",
                      lines)

    def test_dch_main_meta_closes_and_bug_numbers(self):
        self.add_file("closes", "test file",
                      msg="""test non-debian closes 1\n\nExample: EX-123""")
        self.add_file("closes1", "test file",
                      msg="""test non-debian closes 2\n\nExample: EX-5678""")
        options = ["--meta", '--meta-closes-bugnum=ex-\d+',
                   '--meta-closes=Example']
        lines = self.run_dch(options)
        self.assertIn("""  * test non-debian closes 1 (Example: EX-123)\n""",
                      lines)
        self.assertIn("""  * test non-debian closes 2 (Example: EX-5678)\n""",
                      lines)
