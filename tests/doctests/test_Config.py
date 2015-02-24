# vim: set fileencoding=utf-8 :

"""
Test L{gbp.config.GbpConfArgParser}
Test L{gbp.config.GbpConfArgParserDebian}
"""

from .. import context  # noqa: F401


def test_option_parser():
    """
    Methods tested:
         - L{gbp.config.GbpConfArgParser.add_conf_file_arg}
         - L{gbp.config.GbpConfArgParser.add_bool_conf_file_arg}

    >>> import gbp.config
    >>> c = gbp.config.GbpConfArgParser.create_parser(prog='common', prefix='test')
    >>> c.add_conf_file_arg('--upstream-branch', dest='upstream')
    >>> c.add_bool_conf_file_arg('--overlay', dest='overlay')
    >>> c.add_bool_conf_file_arg('--track', dest='track')
    """


def test_option_parser_debian():
    """
    Methods tested:
         - L{gbp.config.GbpConfArgParserDebian.add_conf_file_arg}

    >>> import gbp.config
    >>> c = gbp.config.GbpConfArgParserDebian.create_parser(prog='debian')
    >>> c.add_conf_file_arg('--builder', dest='builder')
    Traceback (most recent call last):
    ...
    KeyError: 'builder'
    >>> c.add_conf_file_arg('--builder', dest='builder', help='foo')
    """


def test_option_group():
    """
    Methods tested:
         - L{gbp.config.GbpOptionGroup.add_conf_file_arg}
         - L{gbp.config.GbpOptionGroup.add_bool_conf_file_arg}

    >>> import gbp.config
    >>> c = gbp.config.GbpConfArgParser.create_parser(prog='debian')
    >>> g = c.add_argument_group('wheezy')
    >>> g.add_conf_file_arg('--debian-branch', dest='branch')
    >>> g.add_bool_conf_file_arg('--track', dest='track')
    """


def test_tristate():
    """
    Methods tested:
         - L{gbp.config.GbpConfArgParser.add_conf_file_arg}

    >>> import gbp.config
    >>> c = gbp.config.GbpConfArgParser.create_parser(prog='tristate')
    >>> c.add_conf_file_arg("--color", dest="color", type='tristate')
    >>> options = c.parse_args(['--color=auto'])
    >>> options.color
    auto
    >>> options.color.is_off()
    False
    >>> c = gbp.config.GbpConfArgParser.create_parser(prog='tristate')
    >>> c.add_conf_file_arg("--color", dest="color", type='tristate')
    >>> options = c.parse_args(['--color=off'])
    >>> options.color
    off
    >>> options.color.is_off()
    True
    """


def test_filter():
    """
    The filter option should always parse as a list
    >>> import os
    >>> from gbp.config import GbpConfig
    >>> tmpdir = str(context.new_tmpdir('bar'))
    >>> confname = os.path.join(tmpdir, 'gbp.conf')
    >>> GbpConfig._set_config_file_value('bar', 'filter', 'asdf', filename=confname)
    >>> config = GbpConfig('bar', config_files=[confname])
    >>> config.get_value('filter')
    ['asdf']
    >>> f = open(confname, 'w')
    >>> ret = f.write("[bar]\\nfilter = ['this', 'is', 'a', 'list']\\n")
    >>> f.close()
    >>> config = GbpConfig('bar', config_files=[confname])
    >>> config.get_value('filter')
    ['this', 'is', 'a', 'list']
    """


def test_filters():
    """
    The filter can be given in plural form
    >>> import os
    >>> from gbp.config import GbpConfig, GbpConfArgParser
    >>> tmpdir = str(context.new_tmpdir('bar'))
    >>> confname = os.path.join(tmpdir, 'gbp.conf')
    >>> GbpConfig._set_config_file_value('bar', 'filters', '["abc", "def"]\\n', filename=confname)
    >>> os.environ['GBP_CONF_FILES'] = confname
    >>> parser = GbpConfArgParser.create_parser(prog='bar')
    >>> parser.config.get_value('filter')
    ['abc', 'def']
    >>> del os.environ['GBP_CONF_FILES']
    """
