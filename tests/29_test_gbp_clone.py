# vim: set fileencoding=utf-8 :
from gbp.scripts.clone import vcs_git_url

import os
import unittest
from mock import patch


class TestGbpClone(unittest.TestCase):
    show_src = """
Version: 0.6.22
Standards-Version: 3.9.4
Vcs-Git: git://honk.sigxcpu.org/git/git-buildpackage.git

Version: 0.8.14
Standards-Version: 3.9.8
Vcs-Git: https://git.sigxcpu.org/cgit/git-buildpackage/ -b foo

Version: 0.8.12.2
Standards-Version: 3.9.8
Vcs-Git: https://git.sigxcpu.org/cgit/git-buildpackage/

Version: 0.6.0~git20120601
Standards-Version: 3.9.3
Vcs-Git: git://honk.sigxcpu.org/git/git-buildpackage.git

"""

    @unittest.skipIf(not os.path.exists('/usr/bin/dpkg'), 'Dpkg not found')
    @patch('gbp.scripts.clone.apt_showsrc', return_value=show_src)
    def test_vcs_git_url(self, patch):
        self.assertEqual(vcs_git_url('git-buildpackage'),
                         'https://git.sigxcpu.org/cgit/git-buildpackage/')
