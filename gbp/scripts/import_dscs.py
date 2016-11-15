# vim: set fileencoding=utf-8 :
#
# (C) 2008, 2009, 2010 Guido Guenther <agx@sigxcpu.org>
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
"""Import multiple dsc files into Git in one go"""

import glob
import os
import sys
import tempfile
import gbp.command_wrappers as gbpc
from gbp.deb import DpkgCompareVersions
from gbp.deb.dscfile import DscFile
from gbp.errors import GbpError
from gbp.git import GitRepository, GitRepositoryError
from gbp.scripts import import_dsc
from gbp.config import GbpOptionParser
import gbp.log


class DscCompareVersions(DpkgCompareVersions):
    def __init__(self):
        DpkgCompareVersions.__init__(self)

    def __call__(self, dsc1, dsc2):
        return DpkgCompareVersions.__call__(self, dsc1.version, dsc2.version)


class GitImportDsc(object):
    def __init__(self, args):
        self.args = args

    def importdsc(self, dsc):
        return import_dsc.main(['import-dsc'] + self.args + [dsc.dscfile])


def fetch_snapshots(pkg, downloaddir):
    "Fetch snapshots using debsnap von snapshots.debian.org"
    dscs = None

    gbp.log.info("Downloading snapshots of '%s' to '%s'..." %
                 (pkg, downloaddir))
    debsnap = gbpc.Command("debsnap", ['--force', '--destdir=%s' %
                                       (downloaddir), pkg])
    try:
        debsnap()
    except gbpc.CommandExecFailed:
        if debsnap.retcode == 2:
            gbp.log.warn("Some packages failed to download. Continuing.")
            pass
        else:
            raise

    dscs = glob.glob(os.path.join(downloaddir, '*.dsc'))
    if not dscs:
        raise GbpError('No package downloaded')

    return [os.path.join(downloaddir, dsc) for dsc in dscs]


def set_gbp_conf_files():
    """
    Filter out all gbp.conf files that are local to the git repository and set
    GBP_CONF_FILES accordingly so gbp import-dsc will only use these.
    """
    global_config = GbpOptionParser.get_config_files(no_local=True)
    gbp_conf_files = ':'.join(global_config)
    os.environ['GBP_CONF_FILES'] = gbp_conf_files
    gbp.log.debug("Setting GBP_CONF_FILES to '%s'" % gbp_conf_files)


def print_help():
    print("""Usage: gbp import-dscs [options] [gbp-import-dsc options] /path/to/dsc1 [/path/to/dsc2] ...
       gbp import-dscs --debsnap [options] [gbp-import-dsc options] package

Options:

    --debsnap:            use debsnap command to download packages
    --ignore-repo-config  ignore gbp.conf in git repo
""")


def main(argv):
    dirs = dict(top=os.path.abspath(os.curdir))
    dscs = []
    ret = 0
    verbose = False
    dsc_cmp = DscCompareVersions()
    use_debsnap = False

    try:
        import_args = argv[1:]

        if '--verbose' in import_args:
            verbose = True
        gbp.log.setup(False, verbose)

        if '--ignore-repo-config' in import_args:
            set_gbp_conf_files()
            import_args.remove('--ignore-repo-config')
        # Not using Configparser since we want to pass all unknown options
        # unaltered to gbp import-dsc
        if '--debsnap' in import_args:
            use_debsnap = True
            import_args.remove('--debsnap')
            if import_args == []:
                print_help()
                raise GbpError
            pkg = import_args[-1]
            import_args = import_args[:-1]
        else:
            for arg in argv[::-1]:
                if arg.endswith('.dsc'):
                    dscs.append(DscFile.parse(arg))
                    import_args.remove(arg)

        if not use_debsnap and not dscs:
            print_help()
            raise GbpError

        if use_debsnap:
            dirs['tmp'] = os.path.abspath(tempfile.mkdtemp())
            dscs = [DscFile.parse(f) for f in fetch_snapshots(pkg, dirs['tmp'])]

        dscs.sort(cmp=dsc_cmp)
        importer = GitImportDsc(import_args)

        try:
            repo = GitRepository('.')
            (clean, out) = repo.is_clean()
            if not clean:
                gbp.log.err("Repository has uncommitted changes, "
                            "commit these first: ")
                raise GbpError(out)
            else:
                dirs['pkg'] = dirs['top']
        except GitRepositoryError:
            # no git repository there yet
            dirs['pkg'] = os.path.join(dirs['top'], dscs[0].pkg)

        if importer.importdsc(dscs[0]):
            raise GbpError("Failed to import '%s'" % dscs[0].dscfile)
        os.chdir(dirs['pkg'])

        for dsc in dscs[1:]:
            if importer.importdsc(dsc):
                raise GbpError("Failed to import '%s'" % dscs[0].dscfile)
    except KeyboardInterrupt:
        ret = 1
        gbp.log.err("Interrupted. Aborting.")
    except (GbpError, gbpc.CommandExecFailed, GitRepositoryError) as err:
        if str(err):
            gbp.log.err(err)
        ret = 1
    finally:
        if 'tmp' in dirs:
            gbpc.RemoveTree(dirs['tmp'])()
        os.chdir(dirs['top'])

    if not ret:
        gbp.log.info('Everything imported under %s' % dirs['pkg'])
    return ret


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
