# vim: set fileencoding=utf-8 :
#
# (C) 2006-2011 Guido Guenther <agx@sigxcpu.org>
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
#
"""run commands to build a debian package out of a git repository"""

import ConfigParser
import errno
import os, os.path
import pipes
import sys
import time
import tempfile
import shutil
import gbp.deb as du
from gbp.git import (GitRepositoryError, GitRepository, build_tag)
from gbp.command_wrappers import (Command,
                                  RunAtCommand, CommandExecFailed, PristineTar,
                                  RemoveTree, CatenateTarArchive)
from gbp.config import (GbpOptionParser, GbpOptionGroup)
from gbp.deb.changelog import ChangeLog, NoChangeLogError, ParseChangeLogError
from gbp.errors import GbpError
from glob import glob
import gbp.log
import gbp.notifications

# when we want to reference the index in a treeish context we call it:
index_name = "INDEX"
# when we want to reference the working copy in treeish context we call it:
wc_name = "WC"
# index file name used to export working copy
wc_index = ".git/gbp_index"


def git_archive_submodules(repo, treeish, output, prefix, comp_type, comp_level, comp_opts):
    """
    Create tar.gz of an archive with submodules

    since git-archive always writes an end of tarfile trailer we concatenate
    the generated archives using tar and compress the result.

    Exception handling is left to the caller.
    """

    tarfile = output.rsplit('.', 1)[0]
    tempdir = tempfile.mkdtemp()
    submodule_tarfile = os.path.join(tempdir, "submodule.tar")
    try:
        # generate main tarfile
        repo.archive(format='tar', prefix='%s/' % (prefix),
                     output=tarfile, treeish=treeish)

        # generate each submodule's tarfile and append it to the main archive
        for (subdir, commit) in repo.get_submodules(treeish):
            tarpath = [subdir, subdir[2:]][subdir.startswith("./")]

            gbp.log.debug("Processing submodule  %s (%s)" % (subdir, commit[0:8]))
            repo.archive(format='tar', prefix='%s/%s/' % (prefix, tarpath),
                         output=submodule_tarfile, treeish=commit, cwd=subdir)
            CatenateTarArchive(tarfile)(submodule_tarfile)

        # compress the output
        ret = os.system("%s -%s %s %s" % (comp_type, comp_level, comp_opts, tarfile))
        if ret:
            raise GbpError("Error creating %s: %d" % (output, ret))
    finally:
        shutil.rmtree(tempdir)


def git_archive_single(treeish, output, prefix, comp_type, comp_level, comp_opts):
    """
    Create tar.gz of an archive without submodules

    Exception handling is left to the caller.
    """
    pipe = pipes.Template()
    pipe.prepend("git archive --format=tar --prefix=%s/ %s" % (prefix, treeish), '.-')
    pipe.append('%s -c -%s %s' % (comp_type, comp_level, comp_opts),  '--')
    ret = pipe.copy('', output)
    if ret:
        raise GbpError("Error creating %s: %d" % (output, ret))


def git_archive(repo, cp, output_dir, treeish, comp_type, comp_level, with_submodules):
    "create a compressed orig tarball in output_dir using git_archive"
    try:
        comp_opts = du.compressor_opts[comp_type][0]
    except KeyError:
        raise GbpError, "Unsupported compression type '%s'" % comp_type

    output = os.path.join(output_dir, du.orig_file(cp, comp_type))
    prefix = "%s-%s" % (cp['Source'], cp['Upstream-Version'])

    try:
        if repo.has_submodules() and with_submodules:
            repo.update_submodules()
            git_archive_submodules(repo, treeish, output, prefix,
                                   comp_type, comp_level, comp_opts)

        else:
            git_archive_single(treeish, output, prefix,
                               comp_type, comp_level, comp_opts)
    except CommandExecFailed:
        gbp.log.err("Error generating submodules' archives")
        return False
    except OSError, err:
        gbp.log.err("Error creating %s: %s" % (output, err[0]))
        return False
    except GbpError:
        raise
    except Exception as e:
        gbp.log.err("Error creating %s: %s" % (output, e))
        return False
    return True


def prepare_upstream_tarball(repo, cp, options, tarball_dir, output_dir):
    """
    Make sure we have an upstream tarball. This involves loooking in
    tarball_dir, symlinking or building it.
    """
    options.comp_type = guess_comp_type(repo,
                                        options.comp_type,
                                        cp,
                                        options.tarball_dir)
    orig_file = du.orig_file(cp, options.comp_type)

    # look in tarball_dir first, if found force a symlink to it
    if options.tarball_dir:
        gbp.log.debug("Looking for orig tarball '%s' at '%s'" % (orig_file, tarball_dir))
        if not du.symlink_orig(cp, options.comp_type, tarball_dir, output_dir, force=True):
            gbp.log.info("Orig tarball '%s' not found at '%s'" % (orig_file, tarball_dir))
        else:
            gbp.log.info("Orig tarball '%s' found at '%s'" % (orig_file, tarball_dir))
    # build an orig unless the user forbids it, always build (and overwrite pre-existing) if user forces it
    if options.force_create or (not options.no_create_orig and not du.has_orig(cp, options.comp_type, output_dir)):
        if not pristine_tar_build_orig(repo, cp, output_dir, options):
            git_archive_build_orig(repo, cp, output_dir, options)


#{ Functions to handle export-dir
def export_source(repo, cp, options, dest_dir, tarball_dir):
    """
    Export a verion of the source tree when building in a separate directory

    @param repo: the git repository to export from
    @type repo: L{gbp.git.GitRepository}
    @param cp: the package's changelog
    @param options: options to apply
    @param dest_dir: where to export the source to
    @param tarball_dir: where to fetch the tarball form in overlay mode
    @returns: the temporary directory
    """
    # write a tree of the index if necessary:
    if options.export == index_name:
        tree = repo.write_tree()
    elif options.export == wc_name:
        tree = write_wc(repo)
    else:
        tree = options.export
    if not repo.has_treeish(tree):
        raise GbpError # git-ls-tree printed an error message already

    # Extract orig tarball if git-overlay option is selected:
    if options.overlay:
        if cp.is_native():
            raise GbpError, "Cannot overlay Debian native package"
        extract_orig(os.path.join(tarball_dir, du.orig_file(cp, options.comp_type)), dest_dir)

    gbp.log.info("Exporting '%s' to '%s'" % (options.export, dest_dir))
    if not dump_tree(repo, dest_dir, tree, options.with_submodules):
        raise GbpError


def dump_tree(repo, export_dir, treeish, with_submodules):
    "dump a tree to output_dir"
    output_dir = os.path.dirname(export_dir)
    prefix = os.path.basename(export_dir)

    pipe = pipes.Template()
    pipe.prepend('git archive --format=tar --prefix=%s/ %s' % (prefix, treeish), '.-')
    pipe.append('tar -C %s -xf -' % output_dir,  '-.')
    top = os.path.abspath(os.path.curdir)
    try:
        ret = pipe.copy('', '')
        if ret:
            raise GbpError, "Error in dump_tree archive pipe"

        if with_submodules:
            if repo.has_submodules():
                repo.update_submodules()
            for (subdir, commit) in repo.get_submodules(treeish):
                gbp.log.info("Processing submodule  %s (%s)" % (subdir, commit[0:8]))
                tarpath = [subdir, subdir[2:]][subdir.startswith("./")]
                os.chdir(subdir)
                pipe = pipes.Template()
                pipe.prepend('git archive --format=tar --prefix=%s/%s/ %s' %
                             (prefix, tarpath, commit), '.-')
                pipe.append('tar -C %s -xf -' % output_dir,  '-.')
                ret = pipe.copy('', '')
                os.chdir(top)
                if ret:
                     raise GbpError, "Error in dump_tree archive pipe in submodule %s" % subdir
    except OSError, err:
        gbp.log.err("Error dumping tree to %s: %s" % (output_dir, err[0]))
        return False
    except GbpError, err:
        gbp.log.err(err)
        return False
    except Exception as e:
        gbp.log.err("Error dumping tree to %s: %s" % (output_dir, e))
        return False
    finally:
        os.chdir(top)
    return True


def move_old_export(target):
    """move a build tree away if it exists"""
    try:
        os.mkdir(target)
    except OSError, (e, msg):
        if e == errno.EEXIST:
            os.rename(target, "%s.obsolete.%s" % (target, time.time()))


def write_wc(repo):
    """write out the current working copy as a treeish object"""
    repo.add_files(repo.path, force=True, index_file=wc_index)
    tree = repo.write_tree(index_file=wc_index)
    return tree


def drop_index():
    """drop our custom index"""
    if os.path.exists(wc_index):
        os.unlink(wc_index)


def extract_orig(orig_tarball, dest_dir):
    """extract orig tarball to export dir before exporting from git"""
    gbp.log.info("Extracting %s to '%s'" % (os.path.basename(orig_tarball), dest_dir))

    move_old_export(dest_dir)
    upstream = gbp.deb.UpstreamSource(orig_tarball)
    upstream.unpack(dest_dir)

    # Check if tarball extracts into a single folder or not:
    if upstream.unpacked != dest_dir:
        # If it extracts a single folder, move all of its contents to dest_dir:
        r = glob("%s/*" % upstream.unpacked)
        r.extend(glob("%s/.*" % upstream.unpacked)) # include hidden files and folders
        for f in r:
            os.rename(f, os.path.join(dest_dir, os.path.basename(f)))

        # Remove that single folder:
        os.rmdir(upstream.unpacked)
#}

def prepare_output_dir(dir):
    """Prepare the directory where the build result will be put"""
    output_dir = dir
    if not dir:
        output_dir = '..'
    output_dir = os.path.abspath(output_dir)

    try:
        os.mkdir(output_dir)
    except OSError, (e, msg):
        if e != errno.EEXIST:
            raise GbpError, "Cannot create output dir %s" % output_dir
    return output_dir

def pristine_tar_build_orig(repo, cp, output_dir, options):
    """
    build orig using pristine-tar
    @return: True: orig.tar.gz build, False: noop
    """
    if options.pristine_tar:
        pt = PristineTar()
        if not repo.has_branch(pt.branch):
            gbp.log.warn('Pristine-tar branch "%s" not found' % pt.branch)
        pt.checkout(os.path.join(output_dir, du.orig_file(cp, options.comp_type)))
        return True
    else:
        return False


def git_archive_build_orig(repo, cp, output_dir, options):
    """build orig using git-archive"""
    if options.upstream_tree == 'tag':
        upstream_tree = build_tag(options.upstream_tag, cp['Upstream-Version'])
    elif options.upstream_tree == 'branch':
        upstream_tree = options.upstream_branch
    else:
        raise GbpError, "Unknown value %s" % options.upstream_tree
    gbp.log.info("%s does not exist, creating from '%s'" % (du.orig_file(cp,
                                                            options.comp_type),
                                                            upstream_tree))
    if not repo.has_treeish(upstream_tree):
        raise GbpError # git-ls-tree printed an error message already
    gbp.log.debug("Building upstream tarball with compression '%s -%s'" % (options.comp_type,
                                                                           options.comp_level))
    if not git_archive(repo, cp, output_dir, upstream_tree,
                       options.comp_type, options.comp_level, options.with_submodules):
        raise GbpError, "Cannot create upstream tarball at '%s'" % output_dir


def guess_comp_type(repo, comp_type, cp, tarball_dir):
    """Guess compression type"""

    srcpkg = cp['Source']
    upstream_version = cp['Upstream-Version']

    if comp_type != 'auto':
        comp_type = du.compressor_aliases.get(comp_type, comp_type)
        try:
            dummy = du.compressor_opts[comp_type]
        except KeyError:
            gbp.log.warn("Unknown compression type - guessing.")
            comp_type = 'auto'

    if comp_type == 'auto':
        if not repo.has_branch(PristineTar.branch):
            if not tarball_dir:
                tarball_dir = '..'
            detected = None
            for comp in du.compressor_opts.keys():
                if du.has_orig(cp, comp, tarball_dir):
                    if detected is not None:
                        raise GbpError, "Multiple orig tarballs found."
                    detected = comp
            if detected is not None:
                comp_type = detected
            else:
                comp_type = 'gzip'
        else:
            regex = 'pristine-tar .* %s_%s\.orig.tar\.' % (srcpkg, upstream_version)
            commits = repo.grep_log(regex, PristineTar.branch)
            if commits:
                commit = commits[-1]
                gbp.log.debug("Found pristine-tar commit at '%s'" % commit)
            else:
                commit = PristineTar.branch
            tarball = repo.get_subject(commit)
            comp_type = du.get_compression(tarball)
            gbp.log.debug("Determined compression type '%s'" % comp_type)
            if not comp_type:
                comp_type = 'gzip'
                gbp.log.warn("Unknown compression type of %s, assuming %s" % (tarball, comp_type))
    return comp_type


def setup_pbuilder(options):
    """setup everything to use git-pbuilder"""
    if options.use_pbuilder or options.use_qemubuilder:
        options.builder = 'git-pbuilder'
        options.cleaner = '/bin/true'
        os.environ['DIST'] = options.pbuilder_dist
        if options.pbuilder_arch:
            os.environ['ARCH'] = options.pbuilder_arch
        if options.use_qemubuilder:
            os.environ['BUILDER'] = "qemubuilder"


def parse_args(argv, prefix):
    args = [ arg for arg in argv[1:] if arg.find('--%s' % prefix) == 0 ]
    dpkg_args = [ arg for arg in argv[1:] if arg.find('--%s' % prefix) == -1 ]

    # We handle these although they don't have a --git- prefix
    for arg in [ "--help", "-h", "--version" ]:
        if arg in dpkg_args:
            args.append(arg)

    try:
        parser = GbpOptionParser(command=os.path.basename(argv[0]), prefix=prefix)
    except ConfigParser.ParsingError, err:
        gbp.log.err(err)
        return None, None, None

    tag_group = GbpOptionGroup(parser, "tag options", "options related to git tag creation")
    branch_group = GbpOptionGroup(parser, "branch options", "branch layout options")
    cmd_group = GbpOptionGroup(parser, "external command options", "how and when to invoke external commands and hooks")
    orig_group = GbpOptionGroup(parser, "orig tarball options", "options related to the creation of the orig tarball")
    export_group = GbpOptionGroup(parser, "export build-tree options", "alternative build tree related options")
    parser.add_option_group(tag_group)
    parser.add_option_group(orig_group)
    parser.add_option_group(branch_group)
    parser.add_option_group(cmd_group)
    parser.add_option_group(export_group)

    parser.add_boolean_config_file_option(option_name = "ignore-new", dest="ignore_new")
    parser.add_option("--git-verbose", action="store_true", dest="verbose", default=False,
                      help="verbose command execution")
    parser.add_config_file_option(option_name="color", dest="color", type='tristate')
    parser.add_config_file_option(option_name="notify", dest="notify", type='tristate')
    tag_group.add_option("--git-tag", action="store_true", dest="tag", default=False,
                      help="create a tag after a successful build")
    tag_group.add_option("--git-tag-only", action="store_true", dest="tag_only", default=False,
                      help="don't build, only tag and run the posttag hook")
    tag_group.add_option("--git-retag", action="store_true", dest="retag", default=False,
                      help="don't fail if the tag already exists")
    tag_group.add_boolean_config_file_option(option_name="sign-tags", dest="sign_tags")
    tag_group.add_config_file_option(option_name="keyid", dest="keyid")
    tag_group.add_config_file_option(option_name="debian-tag", dest="debian_tag")
    tag_group.add_config_file_option(option_name="upstream-tag", dest="upstream_tag")
    orig_group.add_config_file_option(option_name="upstream-tree", dest="upstream_tree")
    orig_group.add_boolean_config_file_option(option_name="pristine-tar", dest="pristine_tar")
    orig_group.add_config_file_option(option_name="force-create", dest="force_create",
                      help="force creation of orig.tar.gz", action="store_true")
    orig_group.add_config_file_option(option_name="no-create-orig", dest="no_create_orig",
                      help="don't create orig.tar.gz", action="store_true")
    orig_group.add_config_file_option(option_name="tarball-dir", dest="tarball_dir", type="path",
                      help="location to look for external tarballs")
    orig_group.add_config_file_option(option_name="compression", dest="comp_type",
                      help="Compression type, default is '%(compression)s'")
    orig_group.add_config_file_option(option_name="compression-level", dest="comp_level",
                      help="Compression level, default is '%(compression-level)s'")
    branch_group.add_config_file_option(option_name="upstream-branch", dest="upstream_branch")
    branch_group.add_config_file_option(option_name="debian-branch", dest="debian_branch")
    branch_group.add_boolean_config_file_option(option_name = "ignore-branch", dest="ignore_branch")
    branch_group.add_boolean_config_file_option(option_name = "submodules", dest="with_submodules")
    cmd_group.add_config_file_option(option_name="builder", dest="builder",
                      help="command to build the Debian package, default is '%(builder)s'")
    cmd_group.add_config_file_option(option_name="cleaner", dest="cleaner",
                      help="command to clean the working copy, default is '%(cleaner)s'")
    cmd_group.add_config_file_option(option_name="prebuild", dest="prebuild",
                      help="command to run before a build, default is '%(prebuild)s'")
    cmd_group.add_config_file_option(option_name="postexport", dest="postexport",
                      help="command to run after exporting the source tree, default is '%(postexport)s'")
    cmd_group.add_config_file_option(option_name="postbuild", dest="postbuild",
                      help="hook run after a successful build, default is '%(postbuild)s'")
    cmd_group.add_config_file_option(option_name="posttag", dest="posttag",
                      help="hook run after a successful tag operation, default is '%(posttag)s'")
    cmd_group.add_boolean_config_file_option(option_name="pbuilder", dest="use_pbuilder")
    cmd_group.add_boolean_config_file_option(option_name="qemubuilder", dest="use_qemubuilder")
    cmd_group.add_config_file_option(option_name="dist", dest="pbuilder_dist")
    cmd_group.add_config_file_option(option_name="arch", dest="pbuilder_arch")
    export_group.add_config_file_option(option_name="export-dir", dest="export_dir", type="path",
                      help="before building the package export the source into EXPORT_DIR, default is '%(export-dir)s'")
    export_group.add_config_file_option("export", dest="export",
                      help="export treeish object TREEISH, default is '%(export)s'", metavar="TREEISH")
    export_group.add_option("--git-dont-purge", action="store_false", dest="purge", default=True,
                      help="retain exported package build directory")
    export_group.add_boolean_config_file_option(option_name="overlay", dest="overlay")
    options, args = parser.parse_args(args)

    gbp.log.setup(options.color, options.verbose)
    if options.retag:
        if not options.tag and not options.tag_only:
            gbp.log.err("'--%sretag' needs either '--%stag' or '--%stag-only'" % (prefix, prefix, prefix))
            return None, None, None

    if options.overlay and not options.export_dir:
        gbp.log.err("Overlay must be used with --git-export-dir")
        return None, None, None

    return options, args, dpkg_args


def main(argv):
    retval = 0
    changelog = 'debian/changelog'
    prefix = "git-"
    cp = None

    options, gbp_args, dpkg_args = parse_args(argv, prefix)
    if not options:
        return 1

    try:
        repo = GitRepository(os.path.curdir)
    except GitRepositoryError:
        gbp.log.err("%s is not a git repository" % (os.path.abspath('.')))
        return 1
    else:
        repo_dir = os.path.abspath(os.path.curdir)

    try:
        branch = repo.get_branch()
        Command(options.cleaner, shell=True)()
        if not options.ignore_new:
            (ret, out) = repo.is_clean()
            if not ret:
                gbp.log.err("You have uncommitted changes in your source tree:")
                gbp.log.err(out)
                raise GbpError, "Use --git-ignore-new to ignore."

        if not options.ignore_new and not options.ignore_branch:
            if branch != options.debian_branch:
                gbp.log.err("You are not on branch '%s' but on '%s'" % (options.debian_branch, branch))
                raise GbpError, "Use --git-ignore-branch to ignore or --git-debian-branch to set the branch name."

        try:
            cp = ChangeLog(filename=changelog)
            if cp.is_native():
                major = cp['Debian-Version']
            else:
                major = cp['Upstream-Version']
        except NoChangeLogError:
            raise GbpError, "'%s' does not exist, not a debian package" % changelog
        except ParseChangeLogError, err:
            raise GbpError, "Error parsing Changelog: %s" % err
        except KeyError:
            raise GbpError, "Can't parse version from changelog"

        if not options.tag_only:
            output_dir = prepare_output_dir(options.export_dir)
            tarball_dir = options.tarball_dir or output_dir

            # Get/build the upstream tarball if necessary. We delay this in
            # case of a postexport hook so the hook gets a chance to modify the
            # sources and create different tarballs (#640382)
            # We don't delay it in general since we want to fail early if the
            # tarball is missing.
            if not cp.is_native():
                if options.postexport:
                    gbp.log.info("Postexport hook set, delaying tarball creation")
                else:
                    prepare_upstream_tarball(repo, cp, options, tarball_dir,
                                             output_dir)

            # Export to another build dir if requested:
            if options.export_dir:
                tmp_dir = os.path.join(output_dir, "%s-tmp" % cp['Source'])
                export_source(repo, cp, options, tmp_dir, output_dir)

                # Run postexport hook
                if options.postexport:
                    RunAtCommand(options.postexport, shell=True,
                                 extra_env={'GBP_GIT_DIR': repo.git_dir,
                                            'GBP_TMP_DIR': tmp_dir})(dir=tmp_dir)

                cp = ChangeLog(filename=os.path.join(tmp_dir, 'debian', 'changelog'))
                export_dir = os.path.join(output_dir, "%s-%s" % (cp['Source'], major))
                gbp.log.info("Moving '%s' to '%s'" % (tmp_dir, export_dir))
                move_old_export(export_dir)
                os.rename(tmp_dir, export_dir)

                # Delayed tarball creation in case a postexport hook is used:
                if not cp.is_native() and options.postexport:
                    prepare_upstream_tarball(repo, cp, options, tarball_dir,
                                             output_dir)

            if options.export_dir:
                build_dir = export_dir
            else:
                build_dir = repo_dir

            if options.prebuild:
                RunAtCommand(options.prebuild, shell=True,
                             extra_env={'GBP_GIT_DIR': repo.git_dir,
                                        'GBP_BUILD_DIR': build_dir})(dir=build_dir)

            setup_pbuilder(options)
            # Finally build the package:
            RunAtCommand(options.builder, dpkg_args, shell=True, 
                         extra_env={'GBP_BUILD_DIR': build_dir})(dir=build_dir)
            if options.postbuild:
                arch = os.getenv('ARCH', None) or du.get_arch()
                changes = os.path.abspath("%s/../%s_%s_%s.changes" %
                                          (build_dir, cp['Source'], cp.noepoch, arch))
                gbp.log.debug("Looking for changes file %s" % changes)
                if not os.path.exists(changes):
                    changes = os.path.abspath("%s/../%s_%s_source.changes" %
                                  (build_dir, cp['Source'], cp.noepoch))
                Command(options.postbuild, shell=True,
                        extra_env={'GBP_CHANGES_FILE': changes,
                                   'GBP_BUILD_DIR': build_dir})()
        if options.tag or options.tag_only:
            gbp.log.info("Tagging %s" % cp.version)
            tag = build_tag(options.debian_tag, cp.version)
            if options.retag and repo.has_tag(tag):
                repo.delete_tag(tag)
            repo.create_tag(name=tag, msg="Debian release %s" % cp.version,
                            sign=options.sign_tags, keyid=options.keyid)
            if options.posttag:
                sha = repo.rev_parse("%s^{}" % tag)
                Command(options.posttag, shell=True,
                        extra_env={'GBP_TAG': tag,
                                   'GBP_BRANCH': branch,
                                   'GBP_SHA1': sha})()
    except CommandExecFailed:
        retval = 1
    except GbpError, err:
        if len(err.__str__()):
            gbp.log.err(err)
        retval = 1
    finally:
        drop_index()

    if not options.tag_only:
        if options.export_dir and options.purge and not retval:
            RemoveTree(export_dir)()

        if cp and not gbp.notifications.notify(cp, not retval, options.notify):
            gbp.log.err("Failed to send notification")
            retval = 1

    return retval

if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
