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

def test_parser_fallback():
    """
    Make sure we also parse git-<subcommands> sections if
    gbp <subcommand> was used.

    >>> import os
    >>> from gbp.config import GbpOptionParser
    >>> parser = GbpOptionParser('foo')
    >>> tmpdir = str(context.new_tmpdir('foo'))
    >>> confname = os.path.join(tmpdir, 'gbp.conf')
    >>> parser.config_files = [confname]
    >>> f = open(confname, 'w')
    >>> f.write('[foo]\\nthere = is\\n[git-foo]\\nno = truth\\n')
    >>> f.close()
    >>> parser._parse_config_files()
    >>> parser.config['there']
    'is'
    >>> parser.config['no']
    'truth'
    """

def test_filter():
    """
    The filter option should always parse as a list
    >>> import os
    >>> from gbp.config import GbpOptionParser
    >>> parser = GbpOptionParser('bar')
    >>> tmpdir = str(context.new_tmpdir('bar'))
    >>> confname = os.path.join(tmpdir, 'gbp.conf')
    >>> parser.config_files = [confname]
    >>> f = open(confname, 'w')
    >>> f.write('[bar]\\nfilter = asdf\\n')
    >>> f.close()
    >>> parser._parse_config_files()
    >>> parser.config['filter']
    ['asdf']
    >>> f = open(confname, 'w')
    >>> f.write("[bar]\\nfilter = ['this', 'is', 'a', 'list']\\n")
    >>> f.close()
    >>> parser._parse_config_files()
    >>> parser.config['filter']
    ['this', 'is', 'a', 'list']
    """

