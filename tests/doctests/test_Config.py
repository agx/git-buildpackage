# vim: set fileencoding=utf-8 :

"""
Test L{gbp.config.GbpOptionParser}
Test L{gbp.config.GbpOptionParserDebian}
"""

from .. import context  # noqa: F401


def test_option_parser():
    """
    Methods tested:
         - L{gbp.config.GbpOptionParser.add_config_file_option}
         - L{gbp.config.GbpOptionParser.add_boolean_config_file_option}

    >>> import gbp.config
    >>> c = gbp.config.GbpOptionParser('common', prefix='test')
    >>> c.add_config_file_option(option_name='upstream-branch', dest='upstream')
    >>> c.add_boolean_config_file_option(option_name='overlay', dest='overlay')
    >>> c.add_boolean_config_file_option(option_name='track', dest='track')
    """


def test_option_parser_debian():
    """
    Methods tested:
         - L{gbp.config.GbpOptionParserDebian.add_config_file_option}

    >>> import gbp.config
    >>> c = gbp.config.GbpOptionParserDebian('debian')
    >>> c.add_config_file_option(option_name='builder', dest='builder')
    Traceback (most recent call last):
    ...
    KeyError: 'builder'
    >>> c.add_config_file_option(option_name='builder', dest='builder', help='foo')
    """


def test_option_group():
    """
    Methods tested:
         - L{gbp.config.GbpOptionGroup.add_config_file_option}
         - L{gbp.config.GbpOptionGroup.add_boolean_config_file_option}

    >>> import gbp.config
    >>> c = gbp.config.GbpOptionParser('debian')
    >>> g = gbp.config.GbpOptionGroup(c, 'wheezy')
    >>> g.add_config_file_option(option_name='debian-branch', dest='branch')
    >>> g.add_boolean_config_file_option(option_name='track', dest='track')
    """


def test_tristate():
    """
    Methods tested:
         - L{gbp.config.GbpOptionParser.add_config_file_option}

    >>> import gbp.config
    >>> c = gbp.config.GbpOptionParser('tristate')
    >>> c.add_config_file_option(option_name="color", dest="color", type='tristate')
    >>> options, args= c.parse_args(['--color=auto'])
    >>> options.color
    auto
    """


def test_filter():
    """
    The filter option should always parse as a list
    >>> import os
    >>> from gbp.config import GbpOptionParser
    >>> tmpdir = str(context.new_tmpdir('bar'))
    >>> confname = os.path.join(tmpdir, 'gbp.conf')
    >>> GbpOptionParser._set_config_file_value('bar', 'filter', 'asdf', filename=confname)
    >>> os.environ['GBP_CONF_FILES'] = confname
    >>> parser = GbpOptionParser('bar')
    >>> parser.config['filter']
    ['asdf']
    >>> f = open(confname, 'w')
    >>> ret = f.write("[bar]\\nfilter = ['this', 'is', 'a', 'list']\\n")
    >>> f.close()
    >>> parser = GbpOptionParser('bar')
    >>> parser.config['filter']
    ['this', 'is', 'a', 'list']
    >>> del os.environ['GBP_CONF_FILES']
    """


def test_filters():
    """
    The filter can be given in plural form
    >>> import os
    >>> from gbp.config import GbpOptionParser
    >>> tmpdir = str(context.new_tmpdir('bar'))
    >>> confname = os.path.join(tmpdir, 'gbp.conf')
    >>> GbpOptionParser._set_config_file_value('bar', 'filters', '["abc", "def"]\\n', filename=confname)
    >>> os.environ['GBP_CONF_FILES'] = confname
    >>> parser = GbpOptionParser('bar')
    >>> parser.config['filter']
    ['abc', 'def']
    >>> del os.environ['GBP_CONF_FILES']
    """
