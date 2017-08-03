# vim: set fileencoding=utf-8 :
#
# (C) 2006-2011, 2016 Guido Guenther <agx@sigxcpu.org>
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
"""Common functionality for Debian and RPM buildpackage scripts"""

import os
import os.path
import pipes
from gbp.git import GitRepositoryError
from gbp.pkg.git import PkgGitRepository
from gbp.errors import GbpError
import gbp.log

# when we want to reference the index in a treeish context we call it:
index_name = "INDEX"
# when we want to reference the working copy in treeish context we call it:
wc_name = "WC"


#  Functions to handle export-dir
def dump_tree(repo, export_dir, treeish, with_submodules, recursive=True):
    "dump a tree to output_dir"
    output_dir = os.path.dirname(export_dir)
    prefix = PkgGitRepository.sanitize_prefix(os.path.basename(export_dir))
    if recursive:
        paths = []
    else:
        paths = ["'%s'" % nam.decode() for _mod, typ, _sha, nam in
                 repo.list_tree(treeish) if typ == 'blob']

    pipe = pipes.Template()
    pipe.prepend('git archive --format=tar --prefix=%s %s -- %s' %
                 (prefix, treeish, ' '.join(paths)), '.-')
    pipe.append('tar -C %s -xf -' % output_dir, '-.')
    top = os.path.abspath(os.path.curdir)
    try:
        ret = pipe.copy('', '')
        if ret:
            raise GbpError("Error in dump_tree archive pipe")

        if recursive and with_submodules:
            if repo.has_submodules():
                repo.update_submodules()
            for (subdir, commit) in repo.get_submodules(treeish):
                gbp.log.info("Processing submodule %s (%s)" % (subdir, commit[0:8]))
                tarpath = [subdir, subdir[2:]][subdir.startswith("./")]
                os.chdir(subdir)
                pipe = pipes.Template()
                pipe.prepend('git archive --format=tar --prefix=%s%s/ %s' %
                             (prefix, tarpath, commit), '.-')
                pipe.append('tar -C %s -xf -' % output_dir, '-.')
                ret = pipe.copy('', '')
                os.chdir(top)
                if ret:
                    raise GbpError("Error in dump_tree archive pipe in submodule %s" % subdir)
    except OSError as err:
        gbp.log.err("Error dumping tree to %s: %s" % (output_dir, err[0]))
        return False
    except (GitRepositoryError, GbpError) as err:
        gbp.log.err(err)
        return False
    except Exception as e:
        gbp.log.err("Error dumping tree to %s: %s" % (output_dir, e))
        return False
    finally:
        os.chdir(top)
    return True


def wc_index(repo):
    """Get path of the temporary index file used for exporting working copy"""
    return os.path.join(repo.git_dir, "gbp_index")


def write_wc(repo, force=True):
    """write out the current working copy as a treeish object"""
    index_file = wc_index(repo)
    repo.add_files(repo.path, force=force, index_file=index_file)
    tree = repo.write_tree(index_file=index_file)
    return tree


def drop_index(repo):
    """drop our custom index"""
    index_file = wc_index(repo)
    if os.path.exists(index_file):
        os.unlink(index_file)
