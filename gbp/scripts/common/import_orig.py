# vim: set fileencoding=utf-8 :
#
# (C) 2006, 2007, 2009, 2011 Guido Günther <agx@sigxcpu.org>
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
#
"""Common functionality for import-orig scripts"""
import contextlib
import os
import tempfile
import gbp.command_wrappers as gbpc
import gbp.log

from gbp.errors import GbpError
from gbp.deb.upstreamsource import DebianUpstreamSource

# Try to import readline, since that will cause raw_input to get fancy
# line editing and history capabilities. However, if readline is not
# available, input() will still work.
try:
    import readline  # noqa: F401
except ImportError:
    pass


def orig_needs_repack(upstream_source, options):
    """
    Determine if the upstream sources needs to be repacked

    We repack if
     1. we want to filter out files via filters or post-unpack script and use
        pristine tar since we want to make a filtered tarball available to
        pristine-tar
     2. we don't have a suitable upstream tarball (e.g. zip archive or unpacked dir)
        and want to use filters
     3. we don't have a suitable upstream tarball (e.g. zip archive or unpacked dir)
        and want to use pristine-tar
     4. we don't have a suitable upstream tarball (e.g. zip archive or unpacked dir)
        and want to use a post-unpack script
    """
    if ((options.pristine_tar and options.filter_pristine_tar and
       (options.filters or options.postunpack))):
        return True
    elif not upstream_source.is_orig():
        if len(options.filters):
            return True
        elif options.pristine_tar:
            return True
        elif options.postunpack:
            return True
    return False


def cleanup_tmp_tree(tree):
    """remove a tree of temporary files"""
    try:
        gbpc.RemoveTree(tree)()
    except gbpc.CommandExecFailed:
        gbp.log.err("Removal of tmptree %s failed." % tree)


def is_link_target(target, link):
    """does symlink link already point to target?"""
    if os.path.exists(link):
        if os.path.samefile(target, link):
            return True
    return False


def ask_package_name(default, name_validator_func, err_msg):
    """
    Ask the user for the source package name.
    @param default: The default package name to suggest to the user.
    """
    while True:
        sourcepackage = input("What will be the source package name? [%s] " % default)
        if not sourcepackage:  # No input, use the default.
            sourcepackage = default
        # Valid package name, return it.
        if name_validator_func(sourcepackage):
            return sourcepackage

        # Not a valid package name. Print an extra
        # newline before the error to make the output a
        # bit clearer.
        gbp.log.warn("\nNot a valid package name: '%s'.\n%s" % (sourcepackage, err_msg))


def ask_package_version(default, ver_validator_func, err_msg):
    """
    Ask the user for the upstream package version.
    @param default: The default package version to suggest to the user.
    """
    while True:
        version = input("What is the upstream version? [%s] " % default)
        if not version:  # No input, use the default.
            version = default
        # Valid version, return it.
        if ver_validator_func(version):
            return version

        # Not a valid upstream version. Print an extra
        # newline before the error to make the output a
        # bit clearer.
        gbp.log.warn("\nNot a valid upstream version: '%s'.\n%s" % (version, err_msg))


def repacked_tarball_name(upstream, name, version):
    if upstream.is_orig():
        # Repacked orig tarball needs a different name since there's already
        # one with that name
        name = os.path.join(
            os.path.dirname(upstream.path),
            os.path.basename(upstream.path).replace(".tar", ".gbp.tar"))
    else:
        # non tarballs (zips, unpacked dirs) get the canonical name
        name = os.path.join(
            os.path.dirname(upstream.path),
            "%s_%s.orig.tar.gz" % (name, version))
    return name


def repack_upstream(upstream, name, version, tmpdir, filters):
    """Repack the upstream source tree"""
    name = repacked_tarball_name(upstream, name, version)
    repacked = upstream.pack(name, filters)
    if upstream.is_orig():  # Orig already was a tarball so it was filtered on unpack
        repacked.unpacked = upstream.unpacked
    else:  # otherwise unpack the generated tarball again to get a filtered tree
        if tmpdir:
            cleanup_tmp_tree(tmpdir)
        tmpdir = tempfile.mkdtemp(dir='../')
        repacked.unpack(tmpdir, filters)
    return (repacked, tmpdir)


def download_orig(url: str) -> DebianUpstreamSource:
    """
    Download orig tarball from given URL
    @param url: the download URL
    @type url: C{str}
    @returns: The upstream source tarball
    @rtype: DebianUpstreamSource
    @raises GbpError: on all errors
    """
    CHUNK_SIZE = 4096

    try:
        import requests
    except ImportError:
        raise GbpError("python3-requests not installed")

    tarball = os.path.basename(url)
    target = os.path.join('..', tarball)

    if os.path.exists(target):
        raise GbpError("Failed to download %s: %s already exists" % (url, target))

    try:
        with contextlib.closing(requests.get(url, verify=True, stream=True)) as r:
            r.raise_for_status()
            with open(target, 'wb', CHUNK_SIZE) as target_fd:
                for d in r.iter_content(CHUNK_SIZE):
                    target_fd.write(d)
    except Exception as e:
        if os.path.exists(target):
            os.unlink(target)
        raise GbpError("Failed to download %s: %s" % (url, e))

    sig = '{}.asc'.format(target)
    if os.path.exists(sig):
        gbp.log.debug("Signature {} found for {}".format(target, sig))
        signature = sig
    else:
        signature = None
    return DebianUpstreamSource(target, sig=signature)
