# vim: set fileencoding=utf-8 :

"""
Test L{gbp.config.GbpOptionParser}
Test L{gbp.config.GbpOptionParserDebian}
"""

from . import context

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
