# vim: set fileencoding=utf-8 :
#
# (C) 2011 Guido Günther <agx@sigxcpu.org>
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
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""A Git Repository that keeps a Debian Package"""

import re
from gbp.git import GitRepository, GitRepositoryError
from gbp.deb.pristinetar import DebianPristineTar

class DebianGitRepository(GitRepository):
    """A git repository that holds the source of a Debian package"""

    def __init__(self, path):
        super(DebianGitRepository, self).__init__(path)
        self.pristine_tar = DebianPristineTar(self)

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
        if self.has_tag(tag): # new tags are injective
            # dereference to a commit object
            return self.rev_parse("%s^0" % tag)
        elif self.has_tag(legacy_tag):
            out, ret = self.__git_getoutput('cat-file', args=['-p', legacy_tag])
            if ret:
                return None
            for line in out:
                if line.endswith(" %s\n" % version):
                    # dereference to a commit object
                    return self.rev_parse("%s^0" % legacy_tag)
                elif line.startswith('---'): # GPG signature start
                    return None
        return None

    @staticmethod
    def _build_legacy_tag(format, version):
        """
        Legacy tags (prior to 0.5.5) dropped epochs and didn't honor the '~'

        >>> DebianGitRepository._build_legacy_tag('upstream/%(version)s', '1:2.0~3')
        'upstream/2.0.3'
        """
        if ':' in version: # strip of any epochs
            version = version.split(':', 1)[1]
        version = version.replace('~', '.')
        return format % dict(version=version)

    @staticmethod
    def version_to_tag(format, version):
        """Generate a tag from a given format and a version

        >>> DebianGitRepository.version_to_tag("debian/%(version)s", "0:0~0")
        'debian/0%0_0'
        """
        return format % dict(version=DebianGitRepository._sanitize_version(version))

    @staticmethod
    def _sanitize_version(version):
        """sanitize a version so git accepts it as a tag

        >>> DebianGitRepository._sanitize_version("0.0.0")
        '0.0.0'
        >>> DebianGitRepository._sanitize_version("0.0~0")
        '0.0_0'
        >>> DebianGitRepository._sanitize_version("0:0.0")
        '0%0.0'
        >>> DebianGitRepository._sanitize_version("0%0~0")
        '0%0_0'
        """
        return version.replace('~', '_').replace(':', '%')

    @staticmethod
    def tag_to_version(tag, format):
        """Extract the version from a tag

        >>> DebianGitRepository.tag_to_version("upstream/1%2_3-4", "upstream/%(version)s")
        '1:2~3-4'
        >>> DebianGitRepository.tag_to_version("foo/2.3.4", "foo/%(version)s")
        '2.3.4'
        >>> DebianGitRepository.tag_to_version("foo/2.3.4", "upstream/%(version)s")
        """
        version_re = format.replace('%(version)s',
                                    '(?P<version>[\w_%+-.]+)')
        r = re.match(version_re, tag)
        if r:
            version = r.group('version').replace('_', '~').replace('%', ':')
            return version
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
        Wheter the repo has a I{pristine-tar} branch.

        @return: C{True} if the repo has pristine-tar commits already, C{False}
            otherwise
        @rtype: C{Bool}
        """
        return True if self.has_branch(self.pristine_tar_branch) else False

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
