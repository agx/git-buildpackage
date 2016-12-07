# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
# (C) 2012 Intel Corporation <markus.lehtonen@linux.intel.com>
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
"""provides some rpm source package related helpers"""

import os
import re
import tempfile
from optparse import OptionParser
from collections import defaultdict

import six

import gbp.command_wrappers as gbpc
from gbp.errors import GbpError
from gbp.git import GitRepositoryError
from gbp.patch_series import (PatchSeries, Patch)
import gbp.log
from gbp.pkg import (UpstreamSource, parse_archive_filename)
from gbp.rpm.policy import RpmPkgPolicy
from gbp.rpm.linkedlist import LinkedList
from gbp.rpm.lib_rpm import librpm, get_librpm_log


class NoSpecError(Exception):
    """Spec file parsing error"""
    pass


class MacroExpandError(Exception):
    """Macro expansion in spec file failed"""
    pass


class RpmUpstreamSource(UpstreamSource):
    """Upstream source class for RPM packages"""
    def __init__(self, name, unpacked=None, **kwargs):
        super(RpmUpstreamSource, self).__init__(name,
                                                unpacked,
                                                RpmPkgPolicy,
                                                **kwargs)


class SrcRpmFile(object):
    """Keeps all needed data read from a source rpm"""
    def __init__(self, srpmfile):
        # Do not required signed packages to be able to import
        ts_vsflags = (librpm.RPMVSF_NOMD5HEADER | librpm.RPMVSF_NORSAHEADER |
                      librpm.RPMVSF_NOSHA1HEADER | librpm.RPMVSF_NODSAHEADER |
                      librpm.RPMVSF_NOMD5 | librpm.RPMVSF_NORSA |
                      librpm.RPMVSF_NOSHA1 | librpm.RPMVSF_NODSA)
        srpmfp = open(srpmfile)
        self.rpmhdr = librpm.ts(vsflags=ts_vsflags).hdrFromFdno(srpmfp.fileno())
        srpmfp.close()
        self.srpmfile = os.path.abspath(srpmfile)

    @property
    def version(self):
        """Get the (downstream) version of the RPM package"""
        version = dict(upstreamversion=self.rpmhdr[librpm.RPMTAG_VERSION],
                       release=self.rpmhdr[librpm.RPMTAG_RELEASE])
        if self.rpmhdr[librpm.RPMTAG_EPOCH] is not None:
            version['epoch'] = str(self.rpmhdr[librpm.RPMTAG_EPOCH])
        return version

    @property
    def name(self):
        """Get the name of the RPM package"""
        return self.rpmhdr[librpm.RPMTAG_NAME]

    @property
    def upstreamversion(self):
        """Get the upstream version of the RPM package"""
        return self.rpmhdr[librpm.RPMTAG_VERSION]

    @property
    def packager(self):
        """Get the packager of the RPM package"""
        return self.rpmhdr[librpm.RPMTAG_PACKAGER]

    def unpack(self, dest_dir):
        """
        Unpack the source rpm to tmpdir.
        Leave the cleanup to the caller in case of an error.
        """
        c = gbpc.RunAtCommand('rpm2cpio',
                              [self.srpmfile, '|', 'cpio', '-id'],
                              shell=True, capture_stderr=True)
        c.run_error = "'%s' failed: {stderr_or_reason}" % (" ".join([c.cmd] + c.args))
        c(dir=dest_dir)


class SpecFile(object):
    """Class for parsing/modifying spec files"""
    tag_re = re.compile(r'^(?P<name>[a-z]+)(?P<num>[0-9]+)?\s*:\s*'
                        '(?P<value>\S(.*\S)?)\s*$', flags=re.I)
    directive_re = re.compile(r'^%(?P<name>[a-z]+)(?P<num>[0-9]+)?'
                              '(\s+(?P<args>.*))?$', flags=re.I)
    gbptag_re = re.compile(r'^\s*#\s*gbp-(?P<name>[a-z-]+)'
                           '(\s*:\s*(?P<args>\S.*))?$', flags=re.I)
    # Here "sections" stand for all scripts, scriptlets and other directives,
    # but not macros
    section_identifiers = ('package', 'description', 'prep', 'build', 'install',
                           'clean', 'check', 'pre', 'preun', 'post', 'postun', 'verifyscript',
                           'files', 'changelog', 'triggerin', 'triggerpostin', 'triggerun',
                           'triggerpostun')

    def __init__(self, filename=None, filedata=None):

        self._content = LinkedList()

        # Check args: only filename or filedata can be given, not both
        if filename is None and filedata is None:
            raise NoSpecError("No filename or raw data given for parsing!")
        elif filename and filedata:
            raise NoSpecError("Both filename and raw data given, don't know "
                              "which one to parse!")
        elif filename:
            # Load spec file into our special data structure
            self.specfile = os.path.basename(filename)
            self.specdir = os.path.dirname(os.path.abspath(filename))
            try:
                with open(filename) as spec_file:
                    for line in spec_file.readlines():
                        self._content.append(line)
            except IOError as err:
                raise NoSpecError("Unable to read spec file: %s" % err)
        else:
            self.specfile = None
            self.specdir = None
            for line in filedata.splitlines():
                self._content.append(line + '\n')

        # Use rpm-python to parse the spec file content
        self._filtertags = ("excludearch", "excludeos", "exclusivearch",
                            "exclusiveos", "buildarch")
        self._listtags = self._filtertags + ('source', 'patch',
                                             'requires', 'conflicts', 'recommends',
                                             'suggests', 'supplements', 'enhances',
                                             'provides', 'obsoletes', 'buildrequires',
                                             'buildconflicts', 'buildrecommends',
                                             'buildsuggests', 'buildsupplements',
                                             'buildenhances', 'collections',
                                             'nosource', 'nopatch')
        self._specinfo = self._parse_filtered_spec(self._filtertags)

        # Other initializations
        source_header = self._specinfo.packages[0].header
        self.name = source_header[librpm.RPMTAG_NAME]
        self.upstreamversion = source_header[librpm.RPMTAG_VERSION]
        self.release = source_header[librpm.RPMTAG_RELEASE]
        # rpm-python returns epoch as 'long', convert that to string
        self.epoch = str(source_header[librpm.RPMTAG_EPOCH]) \
            if source_header[librpm.RPMTAG_EPOCH] is not None else None
        self.packager = source_header[librpm.RPMTAG_PACKAGER]
        self._tags = {}
        self._special_directives = defaultdict(list)
        self._gbp_tags = defaultdict(list)

        # Parse extra info from spec file
        self._parse_content()

        # Find 'Packager' tag. Needed to circumvent a bug in python-rpm where
        # spec.sourceHeader[librpm.RPMTAG_PACKAGER] is not reset when a new spec
        # file is parsed
        if 'packager' not in self._tags:
            self.packager = None

        self.orig_src = self._guess_orig_file()

    def _parse_filtered_spec(self, skip_tags):
        """Parse a filtered spec file in rpm-python"""
        skip_tags = [tag.lower() for tag in skip_tags]
        with tempfile.NamedTemporaryFile(prefix='gbp') as filtered:
            filtered.writelines(str(line) for line in self._content
                                if str(line).split(":")[0].strip().lower() not in skip_tags)
            filtered.flush()
            try:
                # Parse two times to circumvent a rpm-python problem where
                # macros are not expanded if used before their definition
                librpm.spec(filtered.name)
                return librpm.spec(filtered.name)
            except ValueError as err:
                rpmlog = get_librpm_log()
                gbp.log.debug("librpm log:\n        %s" %
                              "\n        ".join(rpmlog))
                raise GbpError("RPM error while parsing %s: %s (%s)" %
                               (self.specfile, err, rpmlog[-1]))

    @property
    def version(self):
        """Get the (downstream) version"""
        version = dict(upstreamversion=self.upstreamversion,
                       release=self.release)
        if self.epoch is not None:
            version['epoch'] = self.epoch
        return version

    @property
    def specpath(self):
        """Get the dir/filename"""
        return os.path.join(self.specdir, self.specfile)

    @property
    def ignorepatches(self):
        """Get numbers of ignored patches as a sorted list"""
        if 'ignore-patches' in self._gbp_tags:
            data = self._gbp_tags['ignore-patches'][-1]['args'].split()
            return sorted([int(num) for num in data])
        return []

    def _patches(self):
        """Get all patch tags as a dict"""
        if 'patch' not in self._tags:
            return {}
        return {patch['num']: patch for patch in self._tags['patch']['lines']}

    def _sources(self):
        """Get all source tags as a dict"""
        if 'source' not in self._tags:
            return {}
        return {src['num']: src for src in self._tags['source']['lines']}

    def sources(self):
        """Get all source tags as a dict"""
        return {src['num']: src['linevalue']
                for src in self._sources().values()}

    def _macro_replace(self, matchobj):
        macro_dict = {'name': self.name,
                      'version': self.upstreamversion,
                      'release': self.release}

        if matchobj.group(2) in macro_dict:
            return macro_dict[matchobj.group(2)]
        raise MacroExpandError("Unknown macro '%s'" % matchobj.group(0))

    def macro_expand(self, text):
        """
        Expand the rpm macros (that gbp knows of) in the given text.

        @param text: text to check for macros
        @type text: C{str}
        @return: text with macros expanded
        @rtype: C{str}
        """
        # regexp to match '%{macro}' and '%macro'
        macro_re = re.compile(r'%({)?(?P<macro_name>[a-z_][a-z0-9_]*)(?(1)})', flags=re.I)
        return macro_re.sub(self._macro_replace, text)

    def write_spec_file(self):
        """
        Write, possibly updated, spec to disk
        """
        with open(os.path.join(self.specdir, self.specfile), 'w') as spec_file:
            for line in self._content:
                spec_file.write(str(line))

    def _parse_tag(self, lineobj):
        """Parse tag line"""

        line = str(lineobj)

        matchobj = self.tag_re.match(line)
        if not matchobj:
            return False

        tagname = matchobj.group('name').lower()
        tagnum = int(matchobj.group('num')) if matchobj.group('num') else None
        # 'Source:' tags
        if tagname == 'source':
            tagnum = 0 if tagnum is None else tagnum
        # 'Patch:' tags
        elif tagname == 'patch':
            tagnum = -1 if tagnum is None else tagnum

        # Record all tag locations
        try:
            header = self._specinfo.packages[0].header
            tagvalue = header[getattr(librpm, 'RPMTAG_%s' % tagname.upper())]
        except AttributeError:
            tagvalue = None
        # We don't support "multivalue" tags like "Provides:" or "SourceX:"
        # Rpm python doesn't support many of these, thus the explicit list
        if isinstance(tagvalue, six.integer_types):
            tagvalue = str(tagvalue)
        elif type(tagvalue) is list or tagname in self._listtags:
            tagvalue = None
        elif not tagvalue:
            # Rpm python doesn't give the following, for reason or another
            if tagname not in ('buildroot', 'autoprov', 'autoreq',
                               'autoreqprov') + self._filtertags:
                gbp.log.warn("BUG: '%s:' tag not found by rpm" % tagname)
            tagvalue = matchobj.group('value')
        linerecord = {'line': lineobj,
                      'num': tagnum,
                      'linevalue': matchobj.group('value')}
        if tagname in self._tags:
            self._tags[tagname]['value'] = tagvalue
            self._tags[tagname]['lines'].append(linerecord)
        else:
            self._tags[tagname] = {'value': tagvalue, 'lines': [linerecord]}

        return tagname

    @staticmethod
    def _patch_macro_opts(args):
        """Parse arguments of the '%patch' macro"""

        patchparser = OptionParser(
            prog="%s internal patch macro opts parser" % __name__,
            usage="%prog for " + args)
        patchparser.add_option("-p", dest="strip")
        patchparser.add_option("-s", dest="silence")
        patchparser.add_option("-P", dest="patchnum")
        patchparser.add_option("-b", dest="backup")
        patchparser.add_option("-E", dest="removeempty")
        patchparser.add_option("-F", dest="fuzz")
        arglist = args.split()
        return patchparser.parse_args(arglist)[0]

    @staticmethod
    def _setup_macro_opts(args):
        """Parse arguments of the '%setup' macro"""

        setupparser = OptionParser(
            prog="%s internal setup macro opts parser" % __name__,
            usage="%prog for " + args)
        setupparser.add_option("-n", dest="name")
        setupparser.add_option("-c", dest="create_dir", action="store_true")
        setupparser.add_option("-D", dest="no_delete_dir", action="store_true")
        setupparser.add_option("-T", dest="no_unpack_default",
                               action="store_true")
        setupparser.add_option("-b", dest="unpack_before")
        setupparser.add_option("-a", dest="unpack_after")
        setupparser.add_option("-q", dest="quiet", action="store_true")
        arglist = args.split()
        return setupparser.parse_args(arglist)[0]

    def _parse_directive(self, lineobj):
        """Parse special directive/scriptlet/macro lines"""

        line = str(lineobj)
        matchobj = self.directive_re.match(line)
        if not matchobj:
            return None

        directivename = matchobj.group('name')
        # '%patch' macros
        directiveid = None
        if directivename == 'patch':
            opts = self._patch_macro_opts(matchobj.group('args'))
            if matchobj.group('num'):
                directiveid = int(matchobj.group('num'))
            elif opts.patchnum:
                directiveid = int(opts.patchnum)
            else:
                directiveid = -1

        # Record special directive/scriptlet/macro locations
        if directivename in self.section_identifiers + ('setup', 'patch'):
            linerecord = {'line': lineobj,
                          'id': directiveid,
                          'args': matchobj.group('args')}
            self._special_directives[directivename].append(linerecord)
        return directivename

    def _parse_gbp_tag(self, linenum, lineobj):
        """Parse special git-buildpackage tags"""

        line = str(lineobj)
        matchobj = self.gbptag_re.match(line)
        if matchobj:
            gbptagname = matchobj.group('name').lower()
            if gbptagname not in ('ignore-patches', 'patch-macros'):
                gbp.log.info("Found unrecognized Gbp tag on line %s: '%s'" %
                             (linenum, line))
            if matchobj.group('args'):
                args = matchobj.group('args').strip()
            else:
                args = None
            record = {'line': lineobj, 'args': args}
            self._gbp_tags[gbptagname].append(record)
            return gbptagname

        return None

    def _parse_content(self):
        """
        Go through spec file content line-by-line and (re-)parse info from it
        """
        in_preamble = True
        for linenum, lineobj in enumerate(self._content):
            matched = False
            if in_preamble:
                if self._parse_tag(lineobj):
                    continue
            matched = self._parse_directive(lineobj)
            if matched:
                if matched in self.section_identifiers:
                    in_preamble = False
                continue
            self._parse_gbp_tag(linenum, lineobj)

        # Update sources info (basically possible macros expanded by rpm)
        # And, double-check that we parsed spec content correctly
        patches = self._patches()
        sources = self._sources()
        for name, num, typ in self._specinfo.sources:
            # workaround rpm parsing bug
            if typ == 1 or typ == 9:
                if num in sources:
                    sources[num]['linevalue'] = name
                else:
                    gbp.log.err("BUG: failed to parse all 'Source' tags!")
            elif typ == 2 or typ == 10:
                # Patch tag without any number defined is treated by RPM as
                # having number (2^31-1), we use number -1
                if num >= pow(2, 30):
                    num = -1
                if num in patches:
                    patches[num]['linevalue'] = name
                else:
                    gbp.log.err("BUG: failed to parse all 'Patch' tags!")

    def _delete_tag(self, tag, num):
        """Delete a tag"""
        key = tag.lower()
        tagname = '%s%s' % (tag, num) if num is not None else tag
        if key not in self._tags:
            gbp.log.warn("Trying to delete non-existent tag '%s:'" % tag)
            return None

        sparedlines = []
        prev = None
        for line in self._tags[key]['lines']:
            if line['num'] == num:
                gbp.log.debug("Removing '%s:' tag from spec" % tagname)
                prev = self._content.delete(line['line'])
            else:
                sparedlines.append(line)
        self._tags[key]['lines'] = sparedlines
        if not self._tags[key]['lines']:
            self._tags.pop(key)
        return prev

    def _set_tag(self, tag, num, value, insertafter):
        """Set a tag value"""
        key = tag.lower()
        tagname = '%s%s' % (tag, num) if num is not None else tag
        value = value.strip()
        if not value:
            raise GbpError("Cannot set empty value to '%s:' tag" % tag)

        # Check type of tag, we don't support values for 'multivalue' tags
        try:
            header = self._specinfo.packages[0].header
            tagvalue = header[getattr(librpm, 'RPMTAG_%s' % tagname.upper())]
        except AttributeError:
            tagvalue = None
        tagvalue = None if type(tagvalue) is list else value

        # Try to guess the correct indentation from the previous or next tag
        indent_re = re.compile(r'^([a-z]+([0-9]+)?\s*:\s*)', flags=re.I)
        match = indent_re.match(str(insertafter))
        if not match:
            match = indent_re.match(str(insertafter.next))
        indent = 12 if not match else len(match.group(1))
        text = '%-*s%s\n' % (indent, '%s:' % tagname, value)
        if key in self._tags:
            self._tags[key]['value'] = tagvalue
            for line in reversed(self._tags[key]['lines']):
                if line['num'] == num:
                    gbp.log.debug("Updating '%s:' tag in spec" % tagname)
                    line['line'].set_data(text)
                    line['linevalue'] = value
                    return line['line']

        gbp.log.debug("Adding '%s:' tag after '%s...' line in spec" %
                      (tagname, str(insertafter)[0:20]))
        line = self._content.insert_after(insertafter, text)
        linerec = {'line': line, 'num': num, 'linevalue': value}
        if key in self._tags:
            self._tags[key]['lines'].append(linerec)
        else:
            self._tags[key] = {'value': tagvalue, 'lines': [linerec]}
        return line

    def set_tag(self, tag, num, value, insertafter=None):
        """Update a tag in spec file content"""
        key = tag.lower()
        tagname = '%s%s' % (tag, num) if num is not None else tag
        if key in ('patch', 'vcs'):
            if key in self._tags:
                insertafter = key
            elif insertafter not in self._tags:
                insertafter = 'name'
            after_line = self._tags[insertafter]['lines'][-1]['line']
            if value:
                self._set_tag(tag, num, value, after_line)
            elif key in self._tags:
                self._delete_tag(tag, num)
        else:
            raise GbpError("Setting '%s:' tag not supported" % tagname)

    def _delete_special_macro(self, name, identifier):
        """Delete a special macro line in spec file content"""
        if name != 'patch':
            raise GbpError("Deleting '%s:' macro not supported" % name)

        key = name.lower()
        fullname = '%%%s%s' % (name, identifier)
        sparedlines = []
        prev = None
        for line in self._special_directives[key]:
            if line['id'] == identifier:
                gbp.log.debug("Removing '%s' macro from spec" % fullname)
                prev = self._content.delete(line['line'])
            else:
                sparedlines.append(line)
        self._special_directives[key] = sparedlines
        if not prev:
            gbp.log.warn("Tried to delete non-existent macro '%s'" % fullname)
        return prev

    def _set_special_macro(self, name, identifier, args, insertafter):
        """Update a special macro line in spec file content"""
        key = name.lower()
        fullname = '%%%s%s' % (name, identifier)
        if key != 'patch':
            raise GbpError("Setting '%s' macro not supported" % name)

        updated = 0
        text = "%%%s%d %s\n" % (name, identifier, args)
        for line in self._special_directives[key]:
            if line['id'] == identifier:
                gbp.log.debug("Updating '%s' macro in spec" % fullname)
                line['args'] = args
                line['line'].set_data(text)
                ret = line['line']
                updated += 1
        if not updated:
            gbp.log.debug("Adding '%s' macro after '%s...' line in spec" %
                          (fullname, str(insertafter)[0:20]))
            ret = self._content.insert_after(insertafter, text)
            linerec = {'line': ret, 'id': identifier, 'args': args}
            self._special_directives[key].append(linerec)
        return ret

    def _set_section(self, name, text):
        """Update/create a complete section in spec file."""
        if name not in self.section_identifiers:
            raise GbpError("Not a valid section directive: '%s'" % name)
        # Delete section, if it exists
        if name in self._special_directives:
            if len(self._special_directives[name]) > 1:
                raise GbpError("Multiple %%%s sections found, don't know "
                               "which to update" % name)
            line = self._special_directives[name][0]['line']
            gbp.log.debug("Removing content of %s section" % name)
            while line.next:
                match = self.directive_re.match(str(line.next))
                if match and match.group('name') in self.section_identifiers:
                    break
                self._content.delete(line.next)
        else:
            gbp.log.debug("Adding %s section to the end of spec file" % name)
            line = self._content.append('%%%s\n' % name)
            linerec = {'line': line, 'id': None, 'args': None}
            self._special_directives[name] = [linerec]
        # Add new lines
        gbp.log.debug("Updating content of %s section" % name)
        for linetext in text.splitlines():
            line = self._content.insert_after(line, linetext + '\n')

    def set_changelog(self, text):
        """Update or create the %changelog section"""
        self._set_section('changelog', text)

    def get_changelog(self):
        """Get the %changelog section"""
        text = ''
        if 'changelog' in self._special_directives:
            line = self._special_directives['changelog'][0]['line']
            while line.next:
                line = line.next
                match = self.directive_re.match(str(line))
                if match and match.group('name') in self.section_identifiers:
                    break
                text += str(line)
        return text

    def update_patches(self, patches, commands):
        """Update spec with new patch tags and patch macros"""
        # Remove non-ignored patches
        tag_prev = None
        macro_prev = None
        ignored = self.ignorepatches
        # Remove 'Patch:̈́' tags
        for tag in self._patches().values():
            if not tag['num'] in ignored:
                tag_prev = self._delete_tag('patch', tag['num'])
                # Remove a preceding comment if it seems to originate from GBP
                if re.match("^\s*#.*patch.*auto-generated",
                            str(tag_prev), flags=re.I):
                    tag_prev = self._content.delete(tag_prev)

        # Remove '%patch:' macros
        for macro in self._special_directives['patch']:
            if not macro['id'] in ignored:
                macro_prev = self._delete_special_macro('patch', macro['id'])
                # Remove surrounding if-else
                macro_next = macro_prev.next
                if (str(macro_prev).startswith('%if') and
                        str(macro_next).startswith('%endif')):
                    self._content.delete(macro_next)
                    macro_prev = self._content.delete(macro_prev)

                # Remove a preceding comment line if it ends with '.patch' or
                # '.diff' plus an optional compression suffix
                if re.match("^\s*#.+(patch|diff)(\.(gz|bz2|xz|lzma))?\s*$",
                            str(macro_prev), flags=re.I):
                    macro_prev = self._content.delete(macro_prev)

        if len(patches) == 0:
            return

        # Determine where to add Patch tag lines
        if tag_prev:
            gbp.log.debug("Adding 'Patch' tags in place of the removed tags")
            tag_line = tag_prev
        elif 'patch' in self._tags:
            gbp.log.debug("Adding new 'Patch' tags after the last 'Patch' tag")
            tag_line = self._tags['patch']['lines'][-1]['line']
        elif 'source' in self._tags:
            gbp.log.debug("Didn't find any old 'Patch' tags, adding new "
                          "patches after the last 'Source' tag.")
            tag_line = self._tags['source']['lines'][-1]['line']
        else:
            gbp.log.debug("Didn't find any old 'Patch' or 'Source' tags, "
                          "adding new patches after the last 'Name' tag.")
            tag_line = self._tags['name']['lines'][-1]['line']

        # Determine where to add %patch macro lines
        if 'patch-macros' in self._gbp_tags:
            gbp.log.debug("Adding '%patch' macros after the start marker")
            macro_line = self._gbp_tags['patch-macros'][-1]['line']
        elif macro_prev:
            gbp.log.debug("Adding '%patch' macros in place of the removed "
                          "macros")
            macro_line = macro_prev
        elif self._special_directives['patch']:
            gbp.log.debug("Adding new '%patch' macros after the last existing"
                          "'%patch' macro")
            macro_line = self._special_directives['patch'][-1]['line']
        elif self._special_directives['setup']:
            gbp.log.debug("Didn't find any old '%patch' macros, adding new "
                          "patches after the last '%setup' macro")
            macro_line = self._special_directives['setup'][-1]['line']
        elif self._special_directives['prep']:
            gbp.log.warn("Didn't find any old '%patch' or '%setup' macros, "
                         "adding new patches directly after '%prep' directive")
            macro_line = self._special_directives['prep'][-1]['line']
        else:
            raise GbpError("Couldn't determine where to add '%patch' macros")

        startnum = sorted(ignored)[-1] + 1 if ignored else 0
        gbp.log.debug("Starting autoupdate patch numbering from %s" % startnum)
        # Add a comment indicating gbp generated patch tags
        comment_text = "# Patches auto-generated by git-buildpackage:\n"
        tag_line = self._content.insert_after(tag_line, comment_text)
        for ind, patch in enumerate(patches):
            cmds = commands[patch] if patch in commands else {}
            patchnum = startnum + ind
            tag_line = self._set_tag("Patch", patchnum, patch, tag_line)
            # Add '%patch' macro and a preceding comment line
            comment_text = "# %s\n" % patch
            macro_line = self._content.insert_after(macro_line, comment_text)
            macro_line = self._set_special_macro('patch', patchnum, '-p1',
                                                 macro_line)
            for cmd, args in six.iteritems(cmds):
                if cmd in ('if', 'ifarch'):
                    self._content.insert_before(macro_line, '%%%s %s\n' %
                                                (cmd, args))
                    macro_line = self._content.insert_after(macro_line,
                                                            '%endif\n')
                    # We only support one command per patch, for now
                    break

    def patchseries(self, unapplied=False, ignored=False):
        """Return non-ignored patches of the RPM as a gbp patchseries"""
        series = PatchSeries()
        if 'patch' in self._tags:
            tags = self._patches()
            applied = []
            for macro in self._special_directives['patch']:
                if macro['id'] in tags:
                    applied.append((macro['id'], macro['args']))
            ignored = set() if ignored else set(self.ignorepatches)

            # Put all patches that are applied first in the series
            for num, args in applied:
                if num not in ignored:
                    opts = self._patch_macro_opts(args)
                    strip = int(opts.strip) if opts.strip else 0
                    filename = os.path.basename(tags[num]['linevalue'])
                    series.append(Patch(os.path.join(self.specdir, filename),
                                        strip=strip))
            # Finally, append all unapplied patches to the series, if requested
            if unapplied:
                applied_nums = set([num for num, _args in applied])
                unapplied = set(tags.keys()).difference(applied_nums)
                for num in sorted(unapplied):
                    if num not in ignored:
                        filename = os.path.basename(tags[num]['linevalue'])
                        series.append(Patch(os.path.join(self.specdir,
                                                         filename), strip=0))
        return series

    def _guess_orig_prefix(self, orig):
        """Guess prefix for the orig file"""
        # Make initial guess about the prefix in the archive
        filename = orig['filename']
        name, version = RpmPkgPolicy.guess_upstream_src_version(filename)
        if name and version:
            prefix = "%s-%s/" % (name, version)
        else:
            prefix = orig['filename_base'] + "/"

        # Refine our guess about the prefix
        for macro in self._special_directives['setup']:
            args = macro['args']
            opts = self._setup_macro_opts(args)
            srcnum = None
            if opts.no_unpack_default:
                if opts.unpack_before:
                    srcnum = int(opts.unpack_before)
                elif opts.unpack_after:
                    srcnum = int(opts.unpack_after)
            else:
                srcnum = 0
            if srcnum == orig['num']:
                if opts.create_dir:
                    prefix = ''
                elif opts.name:
                    try:
                        prefix = self.macro_expand(opts.name) + '/'
                    except MacroExpandError as err:
                        gbp.log.warn("Couldn't determine prefix from %%setup "
                                     "macro (%s). Using filename base as a "
                                     "fallback" % err)
                        prefix = orig['filename_base'] + '/'
                else:
                    # RPM default
                    prefix = "%s-%s/" % (self.name, self.upstreamversion)
                break
        return prefix

    def _guess_orig_file(self):
        """
        Try to guess the name of the primary upstream/source archive.
        Returns a dict with all the relevant information.
        """
        orig = None
        sources = self.sources()
        for num, filename in sorted(six.iteritems(sources)):
            src = {'num': num, 'filename': os.path.basename(filename),
                   'uri': filename}
            src['filename_base'], src['archive_fmt'], src['compression'] = \
                parse_archive_filename(os.path.basename(filename))
            if (src['filename_base'].startswith(self.name) and
                    src['archive_fmt']):
                # Take the first archive that starts with pkg name
                orig = src
                break
            # otherwise we take the first archive
            elif not orig and src['archive_fmt']:
                orig = src
            # else don't accept
        if orig:
            orig['prefix'] = self._guess_orig_prefix(orig)

        return orig


def parse_srpm(srpmfile):
    """parse srpm by creating a SrcRpmFile object"""
    try:
        srcrpm = SrcRpmFile(srpmfile)
    except IOError as err:
        raise GbpError("Error reading src.rpm file: %s" % err)
    except librpm.error as err:
        raise GbpError("RPM error while reading src.rpm: %s" % err)

    return srcrpm


def guess_spec_fn(file_list, preferred_name=None):
    """Guess spec file from a list of filenames"""
    specs = []
    for filepath in file_list:
        filename = os.path.basename(filepath)
        # Stop at the first file matching the preferred name
        if filename == preferred_name:
            gbp.log.debug("Found a preferred spec file %s" % filepath)
            specs = [filepath]
            break
        if filename.endswith(".spec"):
            gbp.log.debug("Found spec file %s" % filepath)
            specs.append(filepath)
    if len(specs) == 0:
        raise NoSpecError("No spec file found.")
    elif len(specs) > 1:
        raise NoSpecError("Multiple spec files found (%s), don't know which "
                          "to use." % ', '.join(specs))
    return specs[0]


def guess_spec(topdir, recursive=True, preferred_name=None):
    """Guess a spec file"""
    file_list = []
    if not topdir:
        topdir = '.'
    for root, dirs, files in os.walk(topdir):
        file_list.extend([os.path.join(root, fname) for fname in files])
        if not recursive:
            del dirs[:]
        # Skip .git dir in any case
        if '.git' in dirs:
            dirs.remove('.git')
    return SpecFile(os.path.abspath(guess_spec_fn(file_list, preferred_name)))


def guess_spec_repo(repo, treeish, topdir='', recursive=True, preferred_name=None):
    """
    Try to find/parse the spec file from a given git treeish.
    """
    topdir = topdir.rstrip('/') + ('/') if topdir else ''
    try:
        file_list = [nam for (mod, typ, sha, nam) in
                     repo.list_tree(treeish, recursive, topdir) if typ == 'blob']
    except GitRepositoryError as err:
        raise NoSpecError("Cannot find spec file from treeish %s, Git error: %s"
                          % (treeish, err))
    spec_path = guess_spec_fn(file_list, preferred_name)
    return spec_from_repo(repo, treeish, spec_path)


def spec_from_repo(repo, treeish, spec_path):
    """Get and parse a spec file from a give Git treeish"""
    try:
        spec = SpecFile(filedata=repo.show('%s:%s' % (treeish, spec_path)))
        spec.specdir = os.path.dirname(spec_path)
        spec.specfile = os.path.basename(spec_path)
        return spec
    except GitRepositoryError as err:
        raise NoSpecError("Git error: %s" % err)


def string_to_int(val_str):
    """
    Convert string of possible unit identifier to int.

    @param val_str: value to be converted
    @type val_str: C{str}
    @return: value as integer
    @rtype: C{int}

    >>> string_to_int("1234")
    1234
    >>> string_to_int("123k")
    125952
    >>> string_to_int("1234K")
    1263616
    >>> string_to_int("1M")
    1048576
    """
    units = {'k': 1024,
             'm': 1024**2,
             'g': 1024**3,
             't': 1024**4}

    if val_str[-1].lower() in units:
        return int(val_str[:-1]) * units[val_str[-1].lower()]
    else:
        return int(val_str)


def split_version_str(version):
    """
    Parse full version string and split it into individual "version
    components", i.e. upstreamversion, epoch and release

    @param version: full version of a package
    @type version: C{str}
    @return: individual version components
    @rtype: C{dict}

    >>> sorted(split_version_str("1").items())
    [('epoch', None), ('release', None), ('upstreamversion', '1')]
    >>> sorted(split_version_str("1.2.3-5.3").items())
    [('epoch', None), ('release', '5.3'), ('upstreamversion', '1.2.3')]
    >>> sorted(split_version_str("3:1.2.3").items())
    [('epoch', '3'), ('release', None), ('upstreamversion', '1.2.3')]
    >>> sorted(split_version_str("3:1-0").items())
    [('epoch', '3'), ('release', '0'), ('upstreamversion', '1')]
    """
    ret = {'epoch': None, 'upstreamversion': None, 'release': None}

    e_vr = version.split(":", 1)
    if len(e_vr) == 1:
        v_r = e_vr[0].split("-", 1)
    else:
        ret['epoch'] = e_vr[0]
        v_r = e_vr[1].split("-", 1)
    ret['upstreamversion'] = v_r[0]
    if len(v_r) > 1:
        ret['release'] = v_r[1]

    return ret


def compose_version_str(evr):
    """
    Compose a full version string from individual "version components",
    i.e. epoch, version and release

    @param evr: dict of version components
    @type evr: C{dict} of C{str}
    @return: full version
    @rtype: C{str}

    >>> compose_version_str({'epoch': '', 'upstreamversion': '1.0'})
    '1.0'
    >>> compose_version_str({'epoch': '2', 'upstreamversion': '1.0', 'release': None})
    '2:1.0'
    >>> compose_version_str({'epoch': None, 'upstreamversion': '1', 'release': '0'})
    '1-0'
    >>> compose_version_str({'epoch': '2', 'upstreamversion': '1.0', 'release': '2.3'})
    '2:1.0-2.3'
    >>> compose_version_str({'epoch': '2', 'upstreamversion': '', 'release': '2.3'})
    """
    if 'upstreamversion' in evr and evr['upstreamversion']:
        version = ""
        if 'epoch' in evr and evr['epoch']:
            version += "%s:" % evr['epoch']
        version += evr['upstreamversion']
        if 'release' in evr and evr['release']:
            version += "-%s" % evr['release']
        if version:
            return version
    return None


def filter_version(evr, *keys):
    """
    Remove entry from the version dict

    @param evr: dict of version components
    @type evr: C{dict} of C{str}
    @param keys: keys to remove
    @type keys: C{str}s
    @return: new version dict
    @rtype: C{dict} of C{str}

    >>> filter_version({'epoch': 'foo', 'upstreamversion': 'bar', 'vendor': 'baz'}, 'vendor').keys()
    ['epoch', 'upstreamversion']
    >>> filter_version({'epoch': 'foo', 'upstreamversion': 'bar', 'revision': 'baz'}, 'epoch', 'revision').keys()
    ['upstreamversion']
    """
    return {k: evr[k] for k in evr if k not in keys}


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
