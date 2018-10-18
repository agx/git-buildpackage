import os
import subprocess


VERSION_PY_PATH = 'gbp/version.py'


def _parse_changelog():
    """Get version from debian changelog and write it to gbp/version.py"""
    popen = subprocess.Popen('dpkg-parsechangelog', stdout=subprocess.PIPE)
    out, ret = popen.communicate()
    for line in out.decode('utf-8').split('\n'):
        if line.startswith('Version:'):
            version = line.split(' ')[1].strip()
            return version

    raise ValueError('Could not parse version from debian/changelog')


def _save_version_py(version):
    with open(VERSION_PY_PATH, 'w') as f:
        f.write('"The current gbp version number"\n')
        f.write('gbp_version = "%s"\n' % version)


def _load_version():
    with open(VERSION_PY_PATH, 'r') as f:
        version_py = f.read()
    version_py_globals = {}
    exec(version_py, version_py_globals)
    return version_py_globals['gbp_version']


def parse_and_fetch_version():
    if os.path.exists('debian/changelog'):
        version = _parse_changelog()
        _save_version_py(version)
        # we could return with the version here, but instead we check that
        # the file has been properly written and it can be loaded back

    version = _load_version()
    return version
