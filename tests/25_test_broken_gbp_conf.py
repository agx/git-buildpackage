# vim: set fileencoding=utf-8 :

"""Check if we fail correcdtly on broken gbp.conf"""

from . import context

from . testutils.data import TestCaseWithData
from . testutils.gbplogtester import GbpLogTester

import os
import unittest


class TestBrokenConfig(TestCaseWithData, GbpLogTester):
    """Test that broken config gives a sensible error for all commands"""

    cmds = ['buildpackage',
            'clone',
            'config',
            'create_remote_repo',
            'dch',
            'import_orig',
            'import_dsc',
            'pull',
            'pq',
            'import_srpm',
            'buildpackage_rpm',
            'pq_rpm',
            'rpm_ch']

    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        GbpLogTester.__init__(self)

    def setUp(self):
        tmpdir = str(context.new_tmpdir('bar'))
        confname = os.path.join(tmpdir, 'gbp.conf')
        with open(confname, 'w') as f:
            f.write("this is a broken config\n")
        os.environ['GBP_CONF_FILES'] = confname
        self._capture_log(True)

    def tearDown(self):
        del os.environ['GBP_CONF_FILES']

    @TestCaseWithData.feed(cmds)
    def testBrokenConf(self, cmd):
        module = 'gbp.scripts.%s' % cmd
        try:
            m = __import__(module, globals(), locals(), ['main'], 0)
            ret = m.main([cmd, '--help'])
            self.assertEquals(ret, 3)
        except Exception as e:
            self.assertTrue(False, "Caught '%s'" % e)
        self._check_log(-1, "See 'man gbp.conf' for the format.")
        self._clear_log()

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
