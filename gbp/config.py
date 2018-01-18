# vim: set fileencoding=utf-8:
#
# (C) 2006,2007,2010-2012,2015,2016,2017 Guido Günther <agx@sigxcpu.org>
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, please see
#    <http://www.gnu.org/licenses/>
"""handles command line and config file option parsing for the gbp commands"""

from argparse import (ArgumentParser, ArgumentDefaultsHelpFormatter,
                      ArgumentTypeError)
import configparser
import errno
import os.path
import sys

from gbp.errors import GbpError

try:
    from gbp.version import gbp_version
except ImportError:
    gbp_version = "[Unknown version]"
import gbp.tristate
import gbp.log
from gbp.git import GitRepositoryError, GitRepository

no_upstream_branch_msg = """
Repository does not have branch '%s' for upstream sources. If there is none see
file:///usr/share/doc/git-buildpackage/manual-html/gbp.import.html#GBP.IMPORT.CONVERT
on howto create it otherwise use --upstream-branch to specify it.
"""


class GbpConfig(object):
    """Handles gbp config files"""
    default_config_files = [('/etc/git-buildpackage/gbp.conf', 'system'),
                            ('~/.gbp.conf', 'global'),
                            ('%(top_dir)s/.gbp.conf', None),
                            ('%(top_dir)s/debian/gbp.conf', 'debian'),
                            ('%(git_dir)s/gbp.conf', None)]

    defaults = {'abbrev': 7,
                'allow-unauthenticated': 'False',
                'arch': '',
                'author-date-is-committer-date': 'False',
                'author-is-committer': 'False',
                'bare': 'True',
                'cleaner': '/bin/true',
                'color': 'auto',
                'color-scheme': '',
                'commit': 'False',
                'commit-msg': 'Update changelog for %(version)s release',
                'component': [],
                'compression': 'auto',
                'compression-level': '',
                'create-missing-branches': 'False',
                'customizations': '',
                'dch-opt': [],
                'debian-branch': 'master',
                'debian-tag': 'debian/%(version)s',
                'debian-tag-msg': '%(pkg)s Debian release %(version)s',
                'dist': 'sid',
                'drop': 'False',
                'export': 'HEAD',
                'export-dir': '',
                'filter': [],
                'filter-pristine-tar': 'False',
                'force-create': 'False',
                'full': 'False',
                'git-author': 'False',
                'git-log': '--no-merges',
                'git-ref': 'upstream/latest',
                'hooks': 'True',
                'id-length': '0',
                'ignore-branch': 'False',
                'ignore-new': 'False',
                'ignore-regex': '',
                'import-msg': 'New upstream version %(version)s',
                'interactive': 'True',
                'keyid': '',
                'merge': 'True',
                'merge-mode': 'auto',
                'meta': 'True',
                'meta-closes': 'Closes|LP',
                'meta-closes-bugnum': r'(?:bug|issue)?\#?\s?\d+',
                'multimaint': 'True',
                'multimaint-merge': 'False',
                'no-create-orig': 'False',
                'notify': 'auto',
                'overlay': 'False',
                'patch-num-format': '%04d-',
                'patch-numbers': 'True',
                'pbuilder': 'False',
                'pbuilder-autoconf': 'True',
                'pbuilder-options': '',
                'postbuild': '',
                'postclone': '',
                'postedit': '',
                'postexport': '',
                'postimport': '',
                'posttag': '',
                'pq-from': 'DEBIAN',
                'prebuild': '',
                'pristine-tar': 'False',
                'pristine-tar-commit': 'False',
                'purge': 'True',
                'qemubuilder': 'False',
                'remote-config': '',
                'remote-url-pattern': 'ssh://git.debian.org/git/collab-maint/%(pkg)s.git',
                'renumber': 'False',
                'repo-email': 'DEBIAN',
                'repo-user': 'DEBIAN',
                'rollback': 'True',
                'sign-tags': 'False',
                'snapshot-number': 'snapshot + 1',
                'spawn-editor': 'release',
                'submodules': 'False',
                'symlink-orig': 'True',
                'tarball-dir': '',
                'template-dir': '',
                'time-machine': 1,
                'track': 'True',
                'track-missing': 'False',
                'upstream-branch': 'upstream',
                'upstream-tag': 'upstream/%(version)s',
                'upstream-tree': 'TAG',
                'upstream-vcs-tag': '',
                'urgency': 'medium',
                }

    default_helps = {
        'debian-branch':
            "Branch the Debian package is being developed on",
        'upstream-branch':
            "Upstream branch",
        'upstream-tree':
            "Where to generate the upstream tarball from (tag or branch)",
        'pq-from':
            "How to find the patch queue base. DEBIAN or TAG",
        'debian-tag':
            "Format string for debian tags",
        'debian-tag-msg':
            "Format string for signed debian-tag messages",
        'upstream-tag':
            "Format string for upstream tags",
        'sign-tags':
            "Whether to sign tags",
        'keyid':
            "GPG keyid to sign tags with",
        'import-msg':
            "Format string for commit message used to commit "
            "the upstream tarball",
        'commit-msg':
            "Format string for commit message used to commit the changelog",
        'pristine-tar':
            "Use pristine-tar to create orig tarball",
        'pristine-tar-commit':
            "When generating a tarball commit it to the pristine-tar branch",
        'filter-pristine-tar':
            "Filter pristine-tar when filter option is used",
        'filter':
            "Files to filter out during import (can be given multiple times)",
        'git-author':
            "Use name and email from git-config for changelog trailer",
        'full':
            "Include the full commit message instead of only the first line",
        'meta':
            "Parse meta tags in commit messages",
        'meta-closes':
            "Meta tags for the bts close commands",
        'meta-closes-bugnum':
            "Meta bug number format",
        'ignore-new':
            "Build with uncommitted changes in the source tree",
        'ignore-branch':
            "Build although debian-branch != current branch",
        'overlay':
            "extract orig tarball when using export-dir option",
        'remote-url-pattern':
            "Remote url pattern to create the repo at",
        'multimaint':
            "Note multiple maintainers",
        'multimaint-merge':
            "Merge commits by maintainer",
        'pbuilder':
            "Invoke git-pbuilder for building",
        'dist':
            "Build for this distribution when using git-pbuilder",
        'arch':
            "Build for this architecture when using git-pbuilder",
        'qemubuilder':
            "Invoke git-pbuilder with qemubuilder for building",
        'interactive':
            "Run command interactively",
        'color':
            "Whether to use colored output",
        'color-scheme':
            "Colors to use in output (when color is enabled), format "
            "is '<debug>:<info>:<warning>:<error>', e.g. "
            "'cyan:34::'. Numerical values and color names are "
            "accepted, empty fields indicate using the default.",
        'spawn-editor':
            "Whether to spawn an editor after adding the changelog entry",
        'patch-numbers':
            "Whether to number patch files",
        'patch-num-format':
            "The format specifier for patch number prefixes",
        'renumber':
            "Whether to renumber patches exported from patch queues, "
            "instead of preserving the number specified in 'Gbp-Pq: Name' tags",
        'notify':
            "Whether to send a desktop notification after the build",
        'merge':
            "After the import merge the result to the debian branch",
        'merge-mode':
            "Howto merge the new upstream sources onto the debian branch",
        'track':
            "Set up tracking for remote branches",
        'track-missing':
            "Track missing remote branches",
        'author-is-committer':
            "Use the authors's name also as the committer's name",
        'author-date-is-committer-date':
            "Use the authors's date as the committer's date",
        'create-missing-branches':
            "Create missing branches automatically",
        'submodules':
            "Transparently handle submodules in the upstream tree",
        'postimport':
            "hook run after a successful import",
        'hooks':
            "Enable running all hooks",
        'time-machine':
            "don't try to apply patch queue to head commit only. "
            "Try at most TIME_MACHINE commits back",
        'pbuilder-autoconf':
            "Whether to configure pbuilder automatically",
        'pbuilder-options':
            "Options to pass to pbuilder",
        'template-dir':
            "Template directory used by git init",
        'remote-config':
            "Remote definition in gbp.conf used to create the remote "
            "repository",
        'allow-unauthenticated':
            "Don't verify integrity of downloaded source",
        'symlink-orig':
            "Whether to create a symlink from the upstream tarball "
            "to the orig.tar.gz if needed",
        'purge':
            "Purge exported package build directory.",
        'drop':
            "In case of 'export' drop the patch-queue branch after export",
        'abbrev':
            "abbreviate commits to this length",
        'commit':
            "commit changes after export",
        'rollback':
            "Rollback repository changes when encountering an error",
        'component':
            'component name for additional tarballs',
        'bare':
            "wether to create a bare repository on the remote side.",
        'urgency':
            "Set urgency level",
        'repo-user':
            "Set repo username from the DEBFULLNAME and DEBEMAIL "
            "environment variables ('DEBIAN') or fallback to the "
            "git configuration ('GIT')",
        'repo-email':
            "Set repo email from the DEBFULLNAME and DEBEMAIL "
            "environment variables ('DEBIAN') or fallback to the "
            "git configuration ('GIT')",
    }

    default_config_files = [('/etc/git-buildpackage/gbp.conf', 'system'),
                            ('~/.gbp.conf', 'global'),
                            ('%(top_dir)s/.gbp.conf', None),
                            ('%(top_dir)s/debian/gbp.conf', 'debian'),
                            ('%(git_dir)s/gbp.conf', None)]

    list_opts = ['filter', 'component', 'dch-opt']

    @classmethod
    def get_config_files(cls, no_local=False):
        """
        Get list of config files from the I{GBP_CONF_FILES} environment
        variable.

        @param no_local: don't return the per-repo configuration files
        @type no_local: C{bool}
        @return: list of config files we need to parse
        @rtype: C{list}

        >>> import re
        >>> conf_backup = os.getenv('GBP_CONF_FILES')
        >>> if conf_backup is not None: del os.environ['GBP_CONF_FILES']
        >>> homedir = os.path.expanduser("~")
        >>> files = GbpConfig('prog').get_config_files()
        >>> files_mangled = [re.sub("^%s" % homedir, 'HOME', file) for file in files]
        >>> sorted(files_mangled)
        ['%(git_dir)s/gbp.conf', '%(top_dir)s/.gbp.conf', '%(top_dir)s/debian/gbp.conf', '/etc/git-buildpackage/gbp.conf', 'HOME/.gbp.conf']
        >>> files = GbpConfig('prog').get_config_files(no_local=True)
        >>> files_mangled = [re.sub("^%s" % homedir, 'HOME', file) for file in files]
        >>> sorted(files_mangled)
        ['/etc/git-buildpackage/gbp.conf', 'HOME/.gbp.conf']
        >>> os.environ['GBP_CONF_FILES'] = 'test1:test2'
        >>> GbpConfig('prog').get_config_files()
        ['test1', 'test2']
        >>> del os.environ['GBP_CONF_FILES']
        >>> if conf_backup is not None: os.environ['GBP_CONF_FILES'] = conf_backup
        """
        envvar = os.environ.get('GBP_CONF_FILES')
        files = envvar.split(':') if envvar else [f for (f, _) in cls.default_config_files]
        files = [os.path.expanduser(fname) for fname in files]
        if no_local:
            files = [fname for fname in files if fname.startswith('/')]
        return files

    def _read_config_file(self, repo, filename):
        """Read config file"""
        str_fields = {}
        if repo:
            str_fields['git_dir'] = repo.git_dir
            if not repo.bare:
                str_fields['top_dir'] = repo.path
        try:
            filename = filename % str_fields
        except KeyError:
            # Skip if filename wasn't expanded, i.e. we're not in git repo
            return
        if (repo and
                filename == os.path.join(repo.path, '.gbp.conf') and
                os.path.exists(filename)):
            self._warn_old_gbp_conf(filename)
        self.config_parser.read(filename)

    def __init__(self, command, extra_sections=None, config_files=None):
        self.command = os.path.basename(command[:-3] if command.endswith('.py') else command)
        self.config = {}
        self.config_parser = configparser.SafeConfigParser()
        self._warned_old_gbp_conf = False

        if not config_files:
            config_files = self.get_config_files()
        try:
            self._parse_config_files(config_files, extra_sections)
        except configparser.ParsingError as err:
            raise GbpError(str(err) + "\nSee 'man gbp.conf' for the format.")

    def _warn_old_config_section(self, oldcmd, cmd):
        if not os.getenv("GBP_DISABLE_SECTION_DEPRECATION"):
            gbp.log.warn("Old style config section [%s] found "
                         "please rename to [%s]" % (oldcmd, cmd))

    def _warn_old_gbp_conf(self, gbp_conf):
        if (not os.getenv("GBP_DISABLE_GBP_CONF_DEPRECATION") and
                not self._warned_old_gbp_conf):
            gbp.log.warn("Deprecated configuration file found at %s, "
                         "check gbp.conf(5) for alternatives" % gbp_conf)
            self._warned_old_gbp_conf = True

    @property
    def config_file_sections(self):
        """List of all found config file sections"""
        return self.config_parser.sections()

    @staticmethod
    def _listify(value):
        """
        >>> GbpConfig._listify(None)
        []
        >>> GbpConfig._listify('string')
        ['string']
        >>> GbpConfig._listify('["q", "e", "d"] ')
        ['q', 'e', 'd']
        >>> GbpConfig._listify('[')
        Traceback (most recent call last):
        ...
        configparser.Error: [ is not a proper list
        """
        # filter can be either a list or a string, always build a list:
        if value:
            if value.startswith('['):
                try:
                    return eval(value)
                except SyntaxError:
                    raise configparser.Error("%s is not a proper list" % value)
            else:
                return [value]
        else:
            return []

    def parse_lists(self):
        """
        Parse options that can be given as lists

        Since they take multiple arguments they can also be given in plural form
        e.g. components instead of component.
        """
        for opt in self.list_opts:
            try:
                plural_opt = opt + 's'
                valp = self._listify(self.config.get(plural_opt, None))
                vals = self._listify(self.config[opt])
                if valp and vals:
                    raise configparser.Error("Found %s and %s - use only one" % (valp, vals))
                self.config[opt] = valp or vals
            except ValueError:
                raise configparser.Error("Failed to parse %s: %s" % (opt, self.config[opt]))

    def _parse_config_files(self, config_files, extra_sections=None):
        """Parse the possible config files and take values from appropriate
        sections."""
        parser = self.config_parser
        # Fill in the built in values
        self.config = dict(self.defaults)
        # Update with the values from the defaults section. This is needed
        # in case the config file doesn't have a [<command>] section at all
        try:
            repo = GitRepository(".", toplevel=False)
        except GitRepositoryError:
            repo = None
        # Read all config files
        for filename in config_files:
            self._read_config_file(repo, filename)
        # Update with the values from the defaults section. This is needed
        # in case the config file doesn't have a [<command>] section at all
        self.config.update(dict(parser.defaults()))

        # Make sure we read any legacy sections prior to the real subcommands
        # section i.e. read [gbp-pull] prior to [pull]
        if (self.command.startswith('gbp-') or
                self.command.startswith('git-')):
            cmd = self.command[4:]
            oldcmd = self.command
            if parser.has_section(oldcmd):
                self.config.update(dict(parser.items(oldcmd, raw=True)))
                self._warn_old_config_section(oldcmd, cmd)
        else:
            cmd = self.command
            for prefix in ['gbp', 'git']:
                oldcmd = '%s-%s' % (prefix, self.command)
                if parser.has_section(oldcmd):
                    self.config.update(dict(parser.items(oldcmd, raw=True)))
                    self._warn_old_config_section(oldcmd, cmd)

        # Update with command specific settings
        if parser.has_section(cmd):
            # Don't use items() until we got rid of the compat sections
            # since this pulls in the defaults again
            self.config.update(dict(parser._sections[cmd].items()))

        if extra_sections:
            for section in extra_sections:
                if parser.has_section(section):
                    self.config.update(dict(parser._sections[section].items()))
                else:
                    raise configparser.NoSectionError(
                        "Mandatory section [%s] does not exist." % section)

        self.parse_lists()

    def get_value(self, name):
        """Get a value from configuration"""
        return self.config[name]

    def get_bool_value(self, name):
        """Get a boolean value from configuration"""
        value_str = self.config[name]
        if value_str.lower() in ["true", "1"]:
            value = True
        elif value_str.lower() in ["false", "0"]:
            value = False
        else:
            raise ValueError("Boolean options must be True or False")
        return value

    def get_dual_bool_value(self, name):
        """
        Get configuration file value for dual-boolean arguments.
        Handles no-foo=True and foo=False correctly.
        """
        try:
            value = self.get_bool_value(name)
        except KeyError:
            value = self.get_bool_value("no-%s" % name)
        return value

    def print_help(self, file=None):
        """
        Print an extended help message, listing all options and any
        help text provided with them, to 'file' (default stdout).
        """
        if file is None:
            file = sys.stdout

        encoding = file.encoding if hasattr(file, 'encoding') else 'utf-8'
        try:
            msg = self.format_help()
            if hasattr(file, 'mode') and 'b' in file.mode:
                msg = msg.encode(encoding, "replace")
            file.write(msg)
        except OSError as e:
            if e.errno != errno.EPIPE:
                raise

    @classmethod
    def _name_to_filename(cls, name):
        """
        Translate a name like 'system' to a config file name

        >>> GbpConfig._name_to_filename('foo')
        >>> GbpConfig._name_to_filename('system')
        '/etc/git-buildpackage/gbp.conf'
        >>> GbpConfig._name_to_filename('global')
        '~/.gbp.conf'
        >>> GbpConfig._name_to_filename('debian')
        '%(top_dir)s/debian/gbp.conf'
        """
        for k, v in cls.default_config_files:
            if name == v:
                return k
        else:
            return None

    @classmethod
    def _set_config_file_value(cls, section, option, value, name=None, filename=None):
        """
        Write a config value to a file creating it if needed

        On errors a ConfigParserError is raised
        """
        if not name and not filename:
            raise configparser.Error("Either 'name' or 'filename' must be given")
        if not filename:
            filename = os.path.expanduser(cls._name_to_filename(name))

        # Create e new config parser since we only operate on a single file
        cfg = configparser.RawConfigParser()
        cfg.read(filename)
        if not cfg.has_section(section):
            cfg.add_section(section)
        cfg.set(section, option, value)
        with open(filename, 'w') as fp:
            cfg.write(fp)


def path_type(arg_str):
    """Argument type for directory path strings"""
    value = os.path.expandvars(arg_str)
    return os.path.expanduser(value)


def tristate_type(arg_str):
    """Type for tristate arguments"""
    try:
        value = gbp.tristate.Tristate(arg_str)
    except TypeError:
        raise ArgumentTypeError("invalid value: %r" % arg_str)
    else:
        return value


class GbpConfArgParser(object):
    """
     This class adds GBP-specific feature of argument parser and argument
     groups, i.e. config file options and argument prefixing.  The class is
     basiclly a wrapper around argument parser and argument groups and adds the
     possibility to read defaults from a config file.
    """
    short_opts = {
        'urgency': '-U',
    }

    class _GbpArgParser(ArgumentParser):
        """The "real" argument parser"""
        def __init__(self, **kwargs):
            """The "real" argument parser"""
            prog = kwargs.get('prog')
            if (prog and not
                    (prog.startswith('git-') or prog.startswith('gbp-'))):
                kwargs['prog'] = "gbp %s" % prog
            if 'formatter_class' not in kwargs:
                kwargs['formatter_class'] = ArgumentDefaultsHelpFormatter
            ArgumentParser.__init__(self, **kwargs)
            self.command = prog if prog else self.prog
            self.register('type', 'tristate', tristate_type)
            self.register('type', 'path', path_type)

    def __init__(self, wrapped_instance, prefix, config=None,
                 conf_file_args=None):
        self.wrapped = wrapped_instance
        self.prefix = prefix
        if config:
            self.config = config
        else:
            self.config = GbpConfig(wrapped_instance.command)
        if conf_file_args is None:
            self.conf_file_args = set()
        else:
            self.conf_file_args = conf_file_args

    @classmethod
    def create_parser(cls, prefix='', config=None, **kwargs):
        """Create new GbpConfArgParser"""
        parser = cls._GbpArgParser(**kwargs)
        parser.add_argument('--version', action='version',
                            version='%s %s' % (parser.prog, gbp_version))
        return cls(parser, prefix=prefix, config=config)

    def _get_conf_key(self, *args):
        """Get name of the config file key for an argument"""
        # Use the first arg string by default
        key = args[0]
        # Search for the first "long argument name"
        for arg in args:
            if (len(arg) > 2 and
                    arg[0:2] in [c * 2 for c in self.wrapped.prefix_chars]):
                key = arg
                break
        return key.lstrip(self.wrapped.prefix_chars)

    @staticmethod
    def _is_boolean(**kwargs):
        """Is the to-be-added arg a boolean option"""
        if ('action' in kwargs and
                kwargs['action'] in ('store_true', 'store_false')):
            return True
        return False

    def add_arg(self, *args, **kwargs):
        """Add argument. Handles argument prefixing."""
        if self.prefix and len(args) > 1:
            raise ValueError("Options with prefix cannot have a short option")

        if 'dest' not in kwargs:
            kwargs['dest'] = self._get_conf_key(*args).replace('-', '_')
        args = [arg.replace('--', '--%s' % self.prefix, 1) for arg in args]
        return self.wrapped.add_argument(*args, **kwargs)

    def add_conf_file_arg(self, *args, **kwargs):
        """Add config file argument"""
        name = self._get_conf_key(*args)
        if name in self.short_opts and self.short_opts[name] not in args:
            args += (self.short_opts[name],)

        is_boolean = self._is_boolean(**kwargs)
        if 'default' not in kwargs:
            if is_boolean:
                kwargs['default'] = self.config.get_dual_bool_value(name)
            else:
                kwargs['default'] = self.config.get_value(name)
        self.conf_file_args.add(name)
        if 'help' not in kwargs and name in self.config.default_helps:
            kwargs['help'] = self.config.default_helps[name]
        new_arg = self.add_arg(*args, **kwargs)

        # Automatically add the inverse argument, with inverted default
        if is_boolean:
            kwargs['dest'] = new_arg.dest
            kwargs['help'] = "negates '--%s%s'" % (self.prefix, name)
            kwargs['action'] = 'store_false' \
                if kwargs['action'] == 'store_true' else 'store_true'
            kwargs['default'] = not kwargs['default']
            self.add_arg('--no-%s' % name, **kwargs)

    def add_bool_conf_file_arg(self, *args, **kwargs):
        """Shortcut to adding boolean args"""
        kwargs['action'] = 'store_true'
        self.add_conf_file_arg(*args, **kwargs)

    def _wrap_generator(self, method, *args, **kwargs):
        """Helper for methods returning a new instance"""
        wrapped = self.wrapped.__getattribute__(method)(*args, **kwargs)
        return GbpConfArgParser(wrapped_instance=wrapped,
                                prefix=self.prefix,
                                config=self.config,
                                conf_file_args=self.conf_file_args)

    def add_argument_group(self, *args, **kwargs):
        """Add argument group"""
        return self._wrap_generator('add_argument_group', *args, **kwargs)

    def add_mutually_exclusive_group(self, *args, **kwargs):
        """Add group of mutually exclusive arguments"""
        return self._wrap_generator('add_mutually_exclusive_group',
                                    *args, **kwargs)

    def add_subparsers(self, *args, **kwargs):
        """Add subparsers"""
        return self._wrap_generator('add_subparsers', *args, **kwargs)

    def add_parser(self, *args, **kwargs):
        """Add parser. Only valid for subparser instances!"""
        if 'parents' in kwargs:
            for parser in kwargs['parents']:
                self.conf_file_args.update(parser.conf_file_args)
        return self._wrap_generator('add_parser',
                                    *args, **kwargs)

    def __getattr__(self, name):
        return self.wrapped.__getattribute__(name)

    def get_conf_file_value(self, option_name):
        """
        Query a single interpolated config file value.

        @param option_name: the config file option to look up
        @type option_name: string
        @returns: The config file option value or C{None} if it doesn't exist
        @rtype: C{str} or C{None}
        """
        if option_name in self.conf_file_args:
            return self.config.get_value(option_name)
        else:
            raise KeyError("Invalid option: %s" % option_name)


class GbpConfigDebian(GbpConfig):
    """Config file parser for Debian tools"""
    defaults = dict(GbpConfig.defaults)
    defaults.update({
        'builder': 'debuild -i -I',
    })

    def _warn_old_gbp_conf(self, gbp_conf):
        if os.path.exists("debian/control"):
            GbpConfig._warn_old_gbp_conf(self, gbp_conf)


class GbpConfArgParserDebian(GbpConfArgParser):
    """Joint config and arg parser for Debian tools"""

    def __init__(self, wrapped_instance, prefix, config=None,
                 conf_file_args=None):
        if not config:
            config = GbpConfigDebian(wrapped_instance.command)
        super(GbpConfArgParserDebian, self).__init__(wrapped_instance, prefix,
                                                     config, conf_file_args)


class GbpConfigRpm(GbpConfig):
    """Config file parser for the RPM tools"""
    defaults = dict(GbpConfig.defaults)
    defaults.update({
        'tmp-dir': '/var/tmp/gbp/',
        'vendor': 'Downstream',
        'packaging-branch': 'master',
        'packaging-dir': '',
        'packaging-tag-msg': '%(pkg)s (vendor)s release %(version)s',
        'packaging-tag': 'packaging/%(version)s',
        'export-sourcedir': 'SOURCES',
        'export-specdir': 'SPECS',
        'export-dir': '../rpmbuild',
        'builder': 'rpmbuild',
        'spec-file': '',
        'mock': 'False',
        'dist': '',
        'arch': '',
        'mock-root': '',
        'mock-options': '',
        'native': 'auto',
        'changelog-file': 'auto',
        'changelog-revision': '',
        'spawn-editor': 'always',
        'editor-cmd': 'vim',
        'spec-vcs-tag': '',
    })
    default_helps = dict(GbpConfig.default_helps)
    default_helps.update(
        {
            'tmp-dir':
                "Base directory under which temporary directories are created",
            'vendor':
                "Distribution vendor name",
            'packaging-branch':
                "Branch the packaging is being maintained on, rpm counterpart "
                "of the 'debian-branch' option",
            'packaging-dir':
                "Subdir for RPM packaging files",
            'packaging-tag':
                "Format string for packaging tags, RPM counterpart of the "
                "'debian-tag' option",
            'packaging-tag-msg':
                "Format string for packaging tag messages",
            'spec-file':
                "Spec file to use, causes the packaging-dir option to be "
                "ignored",
            'export-sourcedir':
                "Subdir (under EXPORT_DIR) where packaging sources (other "
                "than the spec file) are exported",
            'export-specdir':
                "Subdir (under EXPORT_DIR) where package spec file is exported",
            'mock':
                "Invoke mock for building using gbp-builder-mock",
            'dist':
                "Build for this distribution when using mock. E.g.: epel-6",
            'arch':
                "Build for this architecture when using mock",
            'mock-root':
                "The mock root (-r) name for building with mock: <dist>-<arch>",
            'mock-options':
                "Options to pass to mock",
            'native':
                "Treat this package as native",
            'changelog-file':
                "Changelog file to be used",
            'changelog-revision':
                "Format string for the revision field in the changelog header. "
                "If empty or not defined the default from packaging policy is "
                "used.",
            'editor-cmd':
                "Editor command to use",
            'git-author':
                "Use name and email from git-config for the changelog header",
            'spec-vcs-tag':
                "Set/update the 'VCS:' tag in the spec file, empty value "
                "removes the tag entirely",
        })

    def _warn_old_gbp_conf(self, gbp_conf):
        # The rpm based tools use $repo/.gbp.conf a lot, don't
        # warn there yet
        pass


class GbpConfArgParserRpm(GbpConfArgParser):
    """Joint config and arg parser for the RPM tools"""

    def __init__(self, wrapped_instance, prefix, config=None,
                 conf_file_args=None):
        if not config:
            config = GbpConfigRpm(wrapped_instance.command)
        super(GbpConfArgParserRpm, self).__init__(wrapped_instance, prefix,
                                                  config, conf_file_args)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
