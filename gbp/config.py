# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
"""handles command line and config file option parsing for the gbp commands"""

from optparse import OptionParser, OptionGroup
from ConfigParser import SafeConfigParser
import os.path
from gbp.gbp_version import gbp_version

class GbpOptionParser(OptionParser):
    """
    Handles commandline options and parsing of config files
    @ivar command: the gbp command we store the options for
    @type command: string
    @ivar prefix: prefix to prepend to all commandline options
    @type prefix: string
    @ivar config: current configuration parameters
    @type config: dict
    @cvar defaults: defaults value of an option if not in the config file or
    given on the command line
    @type defaults: dict
    @cvar config_files: list of config files we parse
    @type config_files: list
    """
    defaults = { 'builder'         : 'debuild -i\.git/ -I.git',
                 'cleaner'         : 'debuild clean',
                 'debian-branch'   : 'master',
                 'upstream-branch' : 'upstream',
                 'pristine-tar'    : 'False',
                 'sign-tags'       : 'False',
                 'no-create-orig'  : 'False',
                 'keyid'           : '',
                 'posttag'         : '',
                 'debian-tag'      : 'debian/%(version)s',
                 'upstream-tag'    : 'upstream/%(version)s',
                 'filter'          : [],
                 'snapshot-number' : 'snapshot + 1',
                 'git-log'         : '--no-merges',
                 'export-dir'      : '',
                 'tarball-dir'     : '',
                 'ignore-new'      : 'False',
                 'meta'            : 'False',
                 'meta-closes'     : 'Closes|LP',
                 'id-length'       : '0',
                 'no-dch'          : 'False',
             }
    config_files = [ '/etc/git-buildpackage/gbp.conf',
                     os.path.expanduser('~/.gbp.conf'),
                     '.gbp.conf',
                     'debian/gbp.conf',
                     '.git/gbp.conf' ]

    def __parse_config_files(self):
        """parse the possible config files and set appropriate values default values"""
        parser = SafeConfigParser(self.defaults)
        parser.read(self.config_files)
        self.config = dict(parser.defaults())
        if parser.has_section(self.command):
            self.config.update(dict(parser.items(self.command, raw=True)))
        # filter can be either a list or a string, always build a list:
        if self.config['filter']:
            if self.config['filter'].startswith('['):
                self.config['filter'] = eval(self.config['filter'])
            else:
                self.config['filter'] = [ self.config['filter'] ]


    def __init__(self, command, prefix='', usage=None):
        self.command = command
        self.prefix = prefix
        self.config = {}
        self.__parse_config_files()
        OptionParser.__init__(self, usage=usage, version='%s %s' % (self.command, gbp_version))

    def get_default(self, option_name, **kwargs):
        default = self.config[option_name]
        if kwargs.has_key('action'):
            if kwargs['action'] in [ 'store_true', 'store_false' ] and self.config[option_name]:
                    if self.config[option_name] in  [ 'True', 'False' ]:
                        default = eval(self.config[option_name])
                    else:
                        raise ValueError, "Boolean options must be True or False"
        return default

    def add_config_file_option(self, option_name, dest, help, **kwargs):
        """
        set a option for the command line parser, the default is read from the config file
        @var option_name: name of the option
        @type option_name: string
        @var dest: where to store this option
        @type dest: string
        @var help: help text
        @type help: string
        """
        OptionParser.add_option(self, "--%s%s" % (self.prefix, option_name), dest=dest,
                                default=self.get_default(option_name, **kwargs),
                                help=help % self.config, **kwargs)

class GbpOptionGroup(OptionGroup):
    def add_config_file_option(self, option_name, dest, help, **kwargs):
        """
        set a option for the command line parser, the default is read from the config file
        @var option_name: name of the option
        @type option_name: string
        @var dest: where to store this option
        @type dest: string
        @var help: help text
        @type help: string
        """
        OptionGroup.add_option(self, "--%s%s" % (self.parser.prefix, option_name), dest=dest,
                                default=self.parser.get_default(option_name, **kwargs),
                                help=help % self.parser.config, **kwargs)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
