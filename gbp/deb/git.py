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

import re
from gbp.git import GitRepository, GitRepositoryError
from gbp.deb.pristinetar import DebianPristineTar
from gbp.format import format_str

import gbp.log


class DebianGitRepository(GitRepository):
    """A git repository that holds the source of a Debian package"""

    version_mangle_re = (r'%\(version'
                         '%(?P<M>[^%])'
                         '%(?P<R>([^%]|\\%))+'
                         '\)s')

    def __init__(self, path):
        super(DebianGitRepository, self).__init__(path)
        self.pristine_tar = DebianPristineTar(self)

    def tree_drop_dirs(self, tree, dirs):
        """
        Drop the given top level dirs from the given git tree
        returning a new tree object.
        """
        objs = self.list_tree(tree)
        new_tree_objs = []

        for m, t, s, n in objs:
            if not (n in dirs and t == 'tree'):
                new_tree_objs.append((m, t, s, n))
        new_tree = self.make_tree(new_tree_objs)
        return new_tree

    def tree_get_dir(self, tree, dir):
        """
        Get the SHA1 of directory in a given tree
        """
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
        pattern = upstream_tag_format % dict(version='*')
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

    def create_pristinetar_commits(self, upstream_tree, tarball, component_tarballs):
        """
        Create pristine-tar commits for a package with main tarball tarball
        and (optionl) component tarballs based on upstream_tree

        @param tarball: path to main tarball
        @param component_tarballs: C{list} of C{tuple}s of component
            name and path to additional tarball
        @param upstream_tree: the treeish in the git repo to create the commits against
        """
        components = [c for (c, t) in component_tarballs]
        main_tree = self.tree_drop_dirs(upstream_tree, components)

        for component, name in component_tarballs:
            subtree = self.tree_get_dir(upstream_tree, component)
            if not subtree:
                raise GitRepositoryError("No tree for '%s' found in '%s' to create pristine tar commit from" % (component, upstream_tree))
            gbp.log.debug("Creating pristine tar commit '%s' from '%s'" % (component, subtree))
            self.pristine_tar.commit(name, subtree)
        self.pristine_tar.commit(tarball, main_tree)

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
