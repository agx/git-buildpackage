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
from gbp.format import format_str
from gbp.paths import to_bin
from gbp.pkg.git import PkgGitRepository

import gbp.log


class DebianGitRepository(PkgGitRepository):
    """A git repository that holds the source of a Debian package"""

    version_mangle_re = (r'%\(version'
                         '%(?P<M>[^%])'
                         '%(?P<R>([^%]|\\%))+'
                         '\)s')

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
        Inside the substition string, '%' needs to be escaped. See the
        examples below.

        >>> DebianGitRepository.version_to_tag("debian/%(version)s", "0:0~0")
        'debian/0%0_0'
        >>> DebianGitRepository.version_to_tag("libfoo-%(hversion)s", "1.8.1")
        'libfoo-1-8-1'
        >>> DebianGitRepository.version_to_tag("v%(version%.%_)s", "1.2.3")
        'v1_2_3'
        >>> DebianGitRepository.version_to_tag("%(version%-%\%)s", "0-1.2.3")
        '0%1.2.3'
        """
        f, v = cls._mangle_version(format, version)
        return format_str(f, dict(version=cls._sanitize_version(v),
                                  hversion=cls._sanitize_version(v).replace('.', '-')))

    @classmethod
    def _mangle_version(cls, format, version):
        """
        Basic version mangling to replce single characters

        >>> DebianGitRepository._mangle_version("%(version%-%\%)s", "0-1.2.3")
        ('%(version)s', '0%1.2.3')
        """
        r = re.search(cls.version_mangle_re, format)
        if r:
            f = re.sub(cls.version_mangle_re, "%(version)s", format)
            v = version.replace(r.group('M'), r.group('R').replace('\%', '%'))
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
            v = tag.replace(r.group('R').replace('\%', '%'), r.group('M'))
            return v
        else:
            return tag

    @staticmethod
    def _sanitize_version(version):
        """sanitize a version so git accepts it as a tag

        as descirbed in DEP14

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
        v = re.sub('\.(?=\.|$|lock$)', '.#', version)
        return v.replace('~', '_').replace(':', '%')

    @staticmethod
    def _unsanitize_version(tag):
        """Reverse _sanitize_version

        as descirbed in DEP14

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
        version_re = f.replace('%(version)s', '(?P<version>[\w_%+-.#]+)')
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

    def create_pristine_tar_commits(self, upstream_tree, tarball, component_tarballs):
        """
        Create pristine-tar commits for a package with main tarball tarball
        and (optional) component tarballs based on upstream_tree

        @param tarball: path to main tarball
        @param component_tarballs: C{list} of C{tuple}s of component
            name and path to additional tarball
        @param upstream_tree: the treeish in the git repo to create the commits against
        """
        components = [c for (c, t) in component_tarballs]
        main_tree = self.tree_drop_dirs(upstream_tree, components)

        try:
            for component, name in component_tarballs:
                subtree = self.tree_get_dir(upstream_tree, component)
                if not subtree:
                    raise GitRepositoryError("No tree for '%s' found in '%s' to create "
                                             "pristine tar commit from" % (component, upstream_tree))
                gbp.log.debug("Creating pristine tar commit '%s' from '%s'" % (component, subtree))
                self.pristine_tar.commit(name, subtree, quiet=True)
            self.pristine_tar.commit(tarball, main_tree, quiet=True)
        except CommandExecFailed as e:
            raise GitRepositoryError(str(e))

    def get_pristine_tar_commit(self, source, component=None):
        """
        Get the pristine-tar commit for the given source package's latest version.
        """
        comp = '-%s' % component if component else ''
        return self.pristine_tar.get_commit('%s_%s.orig%s.tar.*' % (source.sourcepkg,
                                                                    source.upstream_version,
                                                                    comp))

    def create_upstream_tarball_via_pristine_tar(self, source, output_dir, comp, component=None):
        output = source.upstream_tarball_name(comp.type, component=component)
        try:
            self.pristine_tar.checkout(source.name, source.upstream_version, comp.type, output_dir,
                                       component=component, quiet=True)
        except Exception as e:
            raise GitRepositoryError("Error creating %s: %s" % (output, e))
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
        @param with_submodules: wether to add submodules
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
        if vcs_tag_format:
            try:
                tag = "%s^{}" % self.version_to_tag(vcs_tag_format, version)
                return [self.rev_parse(tag)]
            except GitRepositoryError:
                raise GitRepositoryError("Can't find upstream vcs tag at '%s'" % tag)
        else:
            return None


# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
