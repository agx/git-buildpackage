# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007,2010,2011 Guido Guenther <agx@sigxcpu.org>
"""handles command line and config file option parsing for the gbp commands"""

from optparse import OptionParser, OptionGroup, Option, OptionValueError
from ConfigParser import SafeConfigParser
from copy import copy
import os.path
try:
    from gbp.gbp_version import gbp_version
except ImportError:
    gbp_version = "[Unknown version]"
import gbp.tristate

no_upstream_branch_msg = """
Repository does not have branch '%s' for upstream sources. If there is none see
file:///usr/share/doc/git-buildpackage/manual-html/gbp.import.html#GBP.IMPORT.CONVERT
on howto create it otherwise use --upstream-branch to specify it.
"""

def expand_path(option, opt, value):
    value = os.path.expandvars(value)
    return os.path.expanduser(value)

def check_tristate(option, opt, value):
    try:
        val = gbp.tristate.Tristate(value)
    except TypeError:
        raise OptionValueError(
            "option %s: invalid value: %r" % (opt, value))
    else:
        return val

class GbpOption(Option):
    TYPES = Option.TYPES + ('path', 'tristate')
    TYPE_CHECKER = copy(Option.TYPE_CHECKER)
    TYPE_CHECKER['path'] = expand_path
    TYPE_CHECKER['tristate'] = check_tristate

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
    @cvar help: help messages
    @type help: dict
    @cvar config_files: list of config files we parse
    @type config_files: list
    """
    defaults = { 'builder'         : 'debuild -i -I',
                 'cleaner'         : 'debuild -d clean',
                 'debian-branch'   : 'master',
                 'upstream-branch' : 'upstream',
                 'pristine-tar'    : 'False',
                 'filter-pristine-tar' : 'False',
                 'sign-tags'       : 'False',
                 'force-create'    : 'False',
                 'no-create-orig'  : 'False',
                 'keyid'           : '',
                 'posttag'         : '',
                 'postbuild'       : '',
                 'prebuild'        : '',
                 'postimport'      : '',
                 'debian-tag'      : 'debian/%(version)s',
                 'upstream-tag'    : 'upstream/%(version)s',
                 'import-msg'      : 'Imported Upstream version %(version)s',
                 'filter'          : [],
                 'snapshot-number' : 'snapshot + 1',
                 'git-log'         : '--no-merges',
                 'export'          : 'HEAD',
                 'export-dir'      : '',
                 'overlay'         : 'False',
                 'tarball-dir'     : '',
                 'ignore-new'      : 'False',
                 'ignore-branch'   : 'False',
                 'meta'            : 'False',
                 'meta-closes'     : 'Closes|LP',
                 'full'            : 'False',
                 'id-length'       : '0',
                 'git-author'      : 'False',
                 'ignore-regex'    : '',
                 'compression'     : 'auto',
                 'compression-level': '9',
                 'remote-url-pattern' : 'ssh://alioth.debian.org/git/collab-maint/%(pkg)s.git',
                 'multimaint'      : 'True',
                 'multimaint-merge': 'False',
                 'pbuilder'        : 'False',
                 'dist'            : 'sid',
                 'arch'            : '',
                 'interactive'     : 'True',
                 'color'           : 'auto',
                 'customizations'  : '',
                 'spawn-editor'    : 'release',
                 'patch-numbers'   : 'True',
                 'notify'          : 'auto',
                 'merge'           : 'True',
                 'track'           : 'True',
                 'author-is-committer': 'False',
                 'author-date-is-committer-date': 'False',
                 'create-missing-branches': 'False',
             }
    help = {
             'debian-branch':
                  "branch the Debian package is being developed on, default is '%(debian-branch)s'",
             'upstream-branch':
                  "upstream branch, default is '%(upstream-branch)s'",
             'debian-tag':
                  "format string for debian tags, default is '%(debian-tag)s'",
             'upstream-tag':
                  "format string for upstream tags, default is '%(upstream-tag)s'",
             'sign-tags':
                  "sign tags, default is '%(sign-tags)s'",
             'keyid':
                  "GPG keyid to sign tags with, default is '%(keyid)s'",
             'import-msg':
                  "format string for commit message, default is '%(import-msg)s'",
             'pristine-tar':
                  "use pristine-tar to create .orig.tar.gz, default is '%(pristine-tar)s'",
             'filter-pristine-tar':
                  "Filter pristine-tar when filter option is used",
             'filter':
                  "files to filter out during import (can be given multiple times)",
             'git-author':
                  "use name and email from git-config for changelog trailer, default is '%(git-author)s'",
             'full':
                  "include the full commit message instead of only the first line, default is '%(full)s'",
             'meta':
                  "parse meta tags in commit messages, default is '%(meta)s'",
             'ignore-new':
                  "build with uncommited changes in the source tree, default is '%(ignore-new)s'",
             'ignore-branch':
                  "build although debian-branch != current branch, default is '%(ignore-new)s'",
             'overlay':
                  "extract orig tarball when using export-dir option, default is '%(overlay)s'",
             'remote-url-pattern':
                  "Remote url pattern to create the repo at, default is '%(remote-url-pattern)s'",
             'multimaint':
                  "Note multiple maintainers, default is '%(multimaint)s'",
             'multimaint-merge':
                  "Merge commits by maintainer, default is '%(multimaint-merge)s'",
             'pbuilder':
                  "Invoke git-pbuilder for building, default is '%(pbuilder)s'",
             'dist':
                  "Build for this distribution when using git-pbuilder, default is '%(dist)s'",
             'arch':
                  "Build for this architecture when using git-pbuilder, default is '%(arch)s'",
             'interactive':
                  "Run command interactive, default is '%(interactive)s'",
             'color':
                  "color output, default is '%(color)s'",
             'spawn-editor':
                  "Whether to spawn an editor after adding the changelog entry, default is '%(spawn-editor)s'",
             'patch-numbers':
                  "Whether to number patch files, default is %(patch-numbers)s",
             'notify':
                  "Whether to send a desktop notification after the build, default is '%(notify)s'",
             'merge':
                  "after the import merge the result to the debian branch, default is '%(merge)s'",
             'track':
                  "set up tracking for remote branches, default is '%(track)s'",
             'author-is-committer':
                  "Use the authors's name also as the comitter's name, default is '%(author-is-committer)s'",
             'author-date-is-committer-date':
                  "Use the authors's date as the comitter's date, default is '%(author-date-is-committer-date)s'",
             'create-missing-branches':
                  "Create missing branches automatically, default is '%(create-missing-branches)s'",
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
        OptionParser.__init__(self, option_class=GbpOption, usage=usage, version='%s %s' % (self.command, gbp_version))

    def _is_boolean(self, dummy, *unused, **kwargs):
        """is option_name a boolean option"""
        ret = False
        try:
            if kwargs['action'] in [ 'store_true', 'store_false' ]:
                ret=True
        except KeyError:
            ret=False
        return ret

    def _get_bool_default(self, option_name):
        """
        get default for boolean options
        this way we can handle no-foo=True and foo=False
        """
        if option_name.startswith('no-'):
            pos = option_name[3:]
            neg = option_name
        else:
            pos = option_name
            neg = "no-%s" % option_name

        try:
            default = self.config[pos]
        except KeyError:
            default = self.config[neg]

        if default.lower() in ["true",  "1" ]:
            val = 'True'
        elif default.lower() in ["false", "0" ]:
            val = 'False'
        else:
            raise ValueError, "Boolean options must be True or False"
        return eval(val)

    def get_default(self, option_name, **kwargs):
        """get the default value"""
        if self._is_boolean(self, option_name, **kwargs):
            default = self._get_bool_default(option_name)
        else:
            default = self.config[option_name]
        return default

    def add_config_file_option(self, option_name, dest, help=None, **kwargs):
        """
        set a option for the command line parser, the default is read from the config file
        @var option_name: name of the option
        @type option_name: string
        @var dest: where to store this option
        @type dest: string
        @var help: help text
        @type help: string
        """
        if not help:
            help = self.help[option_name]
        OptionParser.add_option(self, "--%s%s" % (self.prefix, option_name), dest=dest,
                                default=self.get_default(option_name, **kwargs),
                                help=help % self.config, **kwargs)

    def add_boolean_config_file_option(self, option_name, dest):
        self.add_config_file_option(option_name=option_name, dest=dest, action="store_true")
        neg_help = "negates '--%s%s'" % (self.prefix, option_name)
        self.add_config_file_option(option_name="no-%s" % option_name, dest=dest, help=neg_help, action="store_false")

class GbpOptionGroup(OptionGroup):
    def add_config_file_option(self, option_name, dest, help=None, **kwargs):
        """
        set a option for the command line parser, the default is read from the config file
        @var option_name: name of the option
        @type option_name: string
        @var dest: where to store this option
        @type dest: string
        @var help: help text
        @type help: string
        """
        if not help:
            help = self.parser.help[option_name]
        OptionGroup.add_option(self, "--%s%s" % (self.parser.prefix, option_name), dest=dest,
                                default=self.parser.get_default(option_name, **kwargs),
                                help=help % self.parser.config, **kwargs)

    def add_boolean_config_file_option(self, option_name, dest):
        self.add_config_file_option(option_name=option_name, dest=dest, action="store_true")
        neg_help = "negates '--%s%s'" % (self.parser.prefix, option_name)
        self.add_config_file_option(option_name="no-%s" % option_name, dest=dest, help=neg_help, action="store_false")

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
