# vim: set fileencoding=utf-8 :
#
# (C) 2011,2014 Guido Günther <agx@sigxcpu.org>
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
"""A Git Repository that keeps a Debian Package"""

import os
import re

from gbp.command_wrappers import CommandExecFailed
from gbp.git import GitRepositoryError
from gbp.deb.pristinetar import DebianPristineTar
from gbp.paths import to_bin
from gbp.pkg.git import PkgGitRepository
from gbp.pkg.pkgpolicy import PkgPolicy

import gbp.log


class DebianGitRepository(PkgGitRepository):
    """A git repository that holds the source of a Debian package"""

    version_mangle_re = PkgPolicy.version_mangle_re
    # Extensions to strip from version numbers
    splitexts = ['repack', 'py', 'dfsg', 'ds']

    def __init__(self, *args, **kwargs):
        super(DebianGitRepository, self).__init__(*args, **kwargs)
        self.pristine_tar = DebianPristineTar(self)

    def tree_drop_dirs(self, tree, dirs):
        """
        Drop the given top level dirs from the given git tree
        returning a new tree object.
        """
        objs = self.list_tree(tree)
        new_tree_objs = []
        dirs = [to_bin(d) for d in dirs]

        for m, t, s, n in objs:
            if not (n in dirs and t == 'tree'):
                new_tree_objs.append((m, t, s, n))
        new_tree = self.make_tree(new_tree_objs)
        return new_tree

    def tree_get_dir(self, tree, dir):
        """
        Get the SHA1 of directory in a given tree
        """
        dir = to_bin(dir)
        toplevel = self.list_tree(tree)
        for m, t, s, n in toplevel:
            if n == dir and t == 'tree':
                return s
        return None

    def find_version(self, format, version):
        """
        Check if a certain version is stored in this repo and return the SHA1
        of the related commit. That is, an annotated tag is dereferenced to the
        commit object it points to.

        For legacy tags don't only check the tag itself but also the commit
        message, since the former wasn't injective until release 0.5.5. You
        only need to use this function if you also need to check for legacy
        tags.

        @param format: tag pattern
        @type format: C{str}
        @param version: debian version number
        @type version: C{str}
        @return: sha1 of the commit the tag references to
        @rtype: C{str}
        """
        tag = self.version_to_tag(format, version)
        legacy_tag = self._build_legacy_tag(format, version)
        if self.has_tag(tag):  # new tags are injective
            # dereference to a commit object
            return self.rev_parse("%s^0" % tag)
        elif self.has_tag(legacy_tag):
            out, ret = self._git_getoutput('cat-file', args=['-p', legacy_tag])
            if ret:
                return None
            for line in out:
                line = line.decode()
                if line.endswith(" %s\n" % version):
                    # dereference to a commit object
                    return self.rev_parse("%s^0" % legacy_tag)
                elif line.startswith('---'):  # GPG signature start
                    return None
        return None

    def debian_version_from_upstream(self, upstream_tag_format,
                                     upstream_branch, commit='HEAD',
                                     epoch=None, debian_release=True):
        """
        Build the Debian version that a package based on upstream commit
        I{commit} would carry taking into account a possible epoch.

        @param upstream_tag_format: the tag format on the upstream branch
        @type upstream_tag_format: C{str}
        @param upstream_branch: the upstream branch
        @type upstream_branch: C{str}
        @param commit: the commit to search for the latest upstream version
        @param epoch: an epoch to use
        @param debian_release: If set to C{False} don't append a Debian release
          number to the version number
        @returns: a new debian version
        @raises GitRepositoryError: if no upstream tag was found
        """
        pattern = self._unmangle_format(upstream_tag_format) % dict(version='*')
        tag = self.find_branch_tag(commit, upstream_branch, pattern=pattern)
        version = self.tag_to_version(tag, upstream_tag_format)

        if debian_release:
            version += "-1"

        if epoch:
            version = "%s:%s" % (epoch, version)
        return version

    @classmethod
    def _upstream_version_from_debian_upstream(cls, version):
        """
        Convert a Debian upstream version to an upstream version.
        >>> DebianGitRepository._upstream_version_from_debian_upstream(
        ... "1.1.8+dfsg1")
        ('1.1.8', None)
        >>> DebianGitRepository._upstream_version_from_debian_upstream(
        ... "1:5.5.0~dfsg")
        ('5.5.0', None)
        >>> DebianGitRepository._upstream_version_from_debian_upstream(
        ... "0.0~git20160722.0.0cdb66a")
        (None, '0cdb66a')
        >>> DebianGitRepository._upstream_version_from_debian_upstream(
        ... "3:6.04~git20190206.bf6db5b4+dfsg1")
        (None, 'bf6db5b4')
        >>> DebianGitRepository._upstream_version_from_debian_upstream(
        ... "2.3+really2.2")
        ('2.2', None)
        >>> DebianGitRepository._upstream_version_from_debian_upstream(
        ... "42~beta1")
        ('42~beta1', None)
        >>> DebianGitRepository._upstream_version_from_debian_upstream(
        ... "4.99.4+dfsg+really4.10.0+py3")
        ('4.10.0', None)
        >>> DebianGitRepository._upstream_version_from_debian_upstream(
        ... "5.4.1+really5.4.1~repack")
        ('5.4.1', None)
        >>> DebianGitRepository._upstream_version_from_debian_upstream(
        ... "0.0~git20190103.40eba7e+really0.0~git20181023.b4e2780")
        (None, 'b4e2780')
        >>> DebianGitRepository._upstream_version_from_debian_upstream(
        ... "1.1.0+really1.0.0+git20181028.94f6ae3")
        (None, '94f6ae3')
        >>> DebianGitRepository._upstream_version_from_debian_upstream(
        ... "1.1.0")
        ('1.1.0', None)
        """

        # If version starts with an epoch, remove it.
        m = re.search(r'^[0-9]+:(.*)', version)
        if m:
            version = m.group(1)

        # If version has "really", keep the version starting after "really".
        m = re.search(r'really(.*)', version)
        if m:
            version = m.group(1)

        # If version matches a git snapshot pattern, return the git revision.
        m = re.search(r'[~+]git[0-9]{8}(\.[0-9]+)?\.([0-9a-f]+)', version)
        if m:
            return (None, m.group(2))

        # Strip off common extensions starting with [+~] and return the rest.
        return (re.split(r'[+~]({})'.format('|'.join(cls.splitexts)), version)[0], None)

    @staticmethod
    def _build_legacy_tag(format, version):
        """
        Legacy tags (prior to 0.5.5) dropped epochs and didn't honor the '~'

        >>> DebianGitRepository._build_legacy_tag('upstream/%(version)s', '1:2.0~3')
        'upstream/2.0.3'
        """
        if ':' in version:  # strip of any epochs
            version = version.split(':', 1)[1]
        version = version.replace('~', '.')
        return format % dict(version=version)

    @classmethod
    def version_to_tag(cls, format, version):
        """Generate a tag from a given format and a version

        %(version)s provides a clean version that works as a git tag.

        %(hversion)s provides the same thing, but with '.' replaced with '-'.
        hversion is useful for upstreams with tagging policies that prohibit .
        characters.

        %(version%A%B)s provides %(version)s with string 'A' replaced by 'B'.
        This way, simple version mangling is possible via substitution.
        Inside the substitution string, '%' needs to be escaped. See the
        examples below.

        >>> DebianGitRepository.version_to_tag("debian/%(version)s", "0:0~0")
        'debian/0%0_0'
        >>> DebianGitRepository.version_to_tag("libfoo-%(hversion)s", "1.8.1")
        'libfoo-1-8-1'
        >>> DebianGitRepository.version_to_tag("v%(version%.%_)s", "1.2.3")
        'v1_2_3'
        >>> DebianGitRepository.version_to_tag(r'%(version%-%\\%)s', "0-1.2.3")
        '0%1.2.3'
        """
        return PkgPolicy.version_subst(format, version, cls._sanitize_version)

    @classmethod
    def _mangle_version(cls, format, version):
        """
        Basic version mangling to replace single characters

        >>> DebianGitRepository._mangle_version(r'%(version%-%\\%)s', "0-1.2.3")
        ('%(version)s', '0%1.2.3')
        """
        r = re.search(cls.version_mangle_re, format)
        if r:
            f = re.sub(cls.version_mangle_re, "%(version)s", format)
            v = version.replace(r.group('M'), r.group('R').replace(r'\%', '%'))
            return f, v
        else:
            return format, version

    @classmethod
    def _unmangle_format(cls, format):
        """
        Reverse of _mangle_version for format
        """
        r = re.search(cls.version_mangle_re, format)
        if r:
            return re.sub(cls.version_mangle_re, "%(version)s", format)
        else:
            return format

    @classmethod
    def _unmangle_version(cls, format, tag):
        """
        Reverse of _mangle_version for version
        """
        r = re.search(cls.version_mangle_re, format)
        if r:
            v = tag.replace(r.group('R').replace(r'\%', '%'), r.group('M'))
            return v
        else:
            return tag

    @staticmethod
    def _sanitize_version(version):
        """sanitize a version so git accepts it as a tag

        as described in DEP14

        >>> DebianGitRepository._sanitize_version("0.0.0")
        '0.0.0'
        >>> DebianGitRepository._sanitize_version("0.0~0")
        '0.0_0'
        >>> DebianGitRepository._sanitize_version("0:0.0")
        '0%0.0'
        >>> DebianGitRepository._sanitize_version("0%0~0")
        '0%0_0'
        >>> DebianGitRepository._sanitize_version("0....0")
        '0.#.#.#.0'
        >>> DebianGitRepository._sanitize_version("0.lock")
        '0.#lock'
        """
        v = re.sub(r'\.(?=\.|$|lock$)', '.#', version)
        return v.replace('~', '_').replace(':', '%')

    @staticmethod
    def _unsanitize_version(tag):
        """Reverse _sanitize_version

        as described in DEP14

        >>> DebianGitRepository._unsanitize_version("1%0_bpo3")
        '1:0~bpo3'
        >>> DebianGitRepository._unsanitize_version("1%0_bpo3.#.")
        '1:0~bpo3..'
        """
        return tag.replace('_', '~').replace('%', ':').replace('#', '')

    @classmethod
    def tag_to_version(cls, tag, format):
        """Extract the version from a tag

        >>> DebianGitRepository.tag_to_version("upstream/1%2_3-4", "upstream/%(version)s")
        '1:2~3-4'
        >>> DebianGitRepository.tag_to_version("foo/2.3.4", "foo/%(version)s")
        '2.3.4'
        >>> DebianGitRepository.tag_to_version("v1-2-3", "v%(version%.%-)s")
        '1.2.3'
        >>> DebianGitRepository.tag_to_version("v1.#.2", "v%(version%.%-)s")
        '1..2'
        >>> DebianGitRepository.tag_to_version("foo/2.3.4", "upstream/%(version)s")
        """
        f = cls._unmangle_format(format)
        version_re = f.replace('%(version)s', r'(?P<version>[\w_%+-.#]+)')
        r = re.match(version_re, tag)
        if r:
            v = cls._unsanitize_version(r.group('version'))
            return cls._unmangle_version(format, v)
        return None

    @property
    def pristine_tar_branch(self):
        """
        The name of the pristine-tar branch, whether it already exists or
        not.
        """
        return DebianPristineTar.branch

    def has_pristine_tar_branch(self):
        """
        Whether the repo has a I{pristine-tar} branch.

        @return: C{True} if the repo has pristine-tar commits already, C{False}
            otherwise
        @rtype: C{Bool}
        """
        return True if self.has_branch(self.pristine_tar_branch) else False

    def create_pristine_tar_commits(self, upstream_tree, sources):
        """
        Create pristine-tar commits for a package with main tarball
        and (optional) component tarballs based on upstream_tree

        @param upstream_tree: the treeish in the git repo to create the commits against
        @param sources: C{list} of tarball as I{UpstreamSource}. First one being the main
                       tarball the other ones additional tarballs.
        """
        components = [t.component for t in sources[1:]]
        main_tree = self.tree_drop_dirs(upstream_tree, components)

        try:
            for source in sources[1:]:
                subtree = self.tree_get_dir(upstream_tree, source.component)
                if not subtree:
                    raise GitRepositoryError("No tree for '%s' found in '%s' to create "
                                             "pristine tar commit from" % (source.component,
                                                                           upstream_tree))
                gbp.log.debug("Creating pristine tar commit '%s' from '%s'" % (source.path, subtree))
                self.pristine_tar.commit(source.path, subtree, signaturefile=source.signaturefile, quiet=True)
            self.pristine_tar.commit(sources[0].path, main_tree, signaturefile=sources[0].signaturefile, quiet=True)
        except CommandExecFailed as e:
            raise GitRepositoryError(str(e))

    def get_pristine_tar_commit(self, source, component=None):
        """
        Get the pristine-tar commit for the given source package's latest version.
        """
        def _esc(s):
            return s.replace('.', '\\.')

        comp = '-%s' % component if component else ''
        source_esc = _esc(source.sourcepkg)
        ver_esc = _esc(source.upstream_version)
        return self.pristine_tar.get_commit('%s_%s\\.orig%s\\.tar.*' % (source_esc,
                                                                        ver_esc,
                                                                        comp))

    def create_upstream_tarball_via_pristine_tar(self, source, output_dir, comp, upstream_signatures, component=None):
        output = source.upstream_tarball_name(comp.type, component=component)
        gbp.log.debug("upstream signature state: %s" % upstream_signatures)
        commit, found_signature = self.get_pristine_tar_commit(source, component)
        if not commit and self.has_pristine_tar_branch():
            raise GitRepositoryError("Cannot find pristine tar commit for archive '%s'" % output)
        if not found_signature and upstream_signatures.is_on():
            raise GitRepositoryError("Cannot find requested upstream signature for archive '%s' in pristine tar commit." % output)
        try:
            signature = False if upstream_signatures.is_off() else found_signature
            self.pristine_tar.checkout(source.name, source.upstream_version, comp.type, output_dir,
                                       component=component, quiet=True, signature=signature)
        except Exception as e:
            raise GitRepositoryError("Error creating %s%s: %s" % (output,
                                                                  " with attached signature file" if signature else "",
                                                                  e))
        return True

    def create_upstream_tarball_via_git_archive(self, source, output_dir, treeish,
                                                comp, with_submodules, component=None):
        """
        Create a compressed orig tarball in output_dir using git archive

        @param source: debian source package
        @type source: L{DebianSource}
        @param output_dir: output directory
        @param type: C{str}
        @param treeish: git treeish
        @type treeish: C{str}
        @param comp: compressor
        @type comp: L{Compressor}
        @param with_submodules: whether to add submodules
        @type with_submodules: C{bool}
        @param component: component to add to tarball name
        @type component: C{str}

        Raises GitRepositoryError in case of an error
        """
        submodules = False
        output = os.path.join(output_dir,
                              source.upstream_tarball_name(comp.type, component=component))
        prefix = "%s-%s" % (source.name, source.upstream_version)

        try:
            if self.has_submodules() and with_submodules:
                submodules = True
                self.update_submodules()
            self.archive_comp(treeish, output, prefix, comp, submodules=submodules)
        except Exception as e:
            raise GitRepositoryError("Error creating %s: %s" % (output, e))
        return True

    def vcs_tag_parent(self, vcs_tag_format, version):
        """If linking to the upstream VCS get the commit id"""
        if not vcs_tag_format:
            return None
        (version, revision) = self._upstream_version_from_debian_upstream(version)
        try:
            if not revision:
                revision = self.version_to_tag(vcs_tag_format, version)
            return [self.rev_parse("%s^{}" % revision)]
        except GitRepositoryError:
            raise GitRepositoryError("Can't find upstream vcs tag/revision at '%s'" % revision)


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
