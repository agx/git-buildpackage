# vim: set fileencoding=utf-8 :

"""Check if --help works"""

from . import context  # noqa: F401

from .testutils.data import TestCaseWithData


class TestHelp(TestCaseWithData):
    """Test help output of gbp commands"""

    deb_cmds = ['buildpackage',
                'config',
                'create_remote_repo',
                'dch',
                'import_orig',
                'import_dsc',
                'pull',
                'pq']

    rpm_cmds = ['buildpackage_rpm',
                'import_srpm',
                'rpm_ch',
                'pq_rpm']

    @TestCaseWithData.feed(deb_cmds + rpm_cmds)
    def testHelp(self, script):
        module = 'gbp.scripts.%s' % script
        m = __import__(module, globals(), locals(), ['main'], 0)
        self.assertRaises(SystemExit,
                          m.main,
                          ['doesnotmatter', '--help'])

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
