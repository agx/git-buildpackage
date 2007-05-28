# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
"""handles command line and config file option parsing for the gbp commands"""

from optparse import OptionParser
from ConfigParser import SafeConfigParser
import os.path

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
    defaults={ 'builder'         : 'debuild',
               'cleaner'	     : 'debuild clean',
               'debian-branch'   : 'master',
               'upstream-branch' : 'upstream',
               'sign-tags'	     : '',		# empty means False
               'keyid'		     : '',
               'posttag'         : '',
               'debian-tag'      : 'debian/%(version)s',
               'upstream-tag'    : 'upstream/%(version)s',
               'filter'          : '',
             }
    config_files=['/etc/git-buildpackage/gbp.conf',
                  os.path.expanduser('~/.gbp.conf'),
                  '.git/gbp.conf' ]

    def __parse_config_files(self):
        """parse the possible config files and set appropriate values default values"""
        parser=SafeConfigParser(self.defaults)
        parser.read(self.config_files)
        self.config=dict(parser.defaults())
        if parser.has_section(self.command):
            self.config=dict(parser.items(self.command, raw=True))

    def __init__(self, command, prefix='', usage=None):
        self.command=command
        self.prefix=prefix
        self.__parse_config_files()
        OptionParser.__init__(self, usage=usage)


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
        OptionParser.add_option(self,"--%s%s" % (self.prefix, option_name), dest=dest,
                                default=self.config[option_name], 
                                help=help % self.config, **kwargs)

# vim:et:ts=4:sw=4:
