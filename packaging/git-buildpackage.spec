# Add --without docs rpmbuild option, i.e. docs are enabled by default
%bcond_without docs

Name:       git-buildpackage
Summary:    Build packages from git
Version:    0.7.0
Release:    0
Group:      Development/Tools/Building
License:    GPLv2
BuildArch:  noarch
URL:        https://honk.sigxcpu.org/piki/projects/git-buildpackage/
Source0:    %{name}_%{version}.tar.gz

# Conditional package names for requirements
%if 0%{?fedora} || 0%{?centos_ver} >= 7
%define dpkg_pkg_name dpkg-dev
%else
%if 0%{?centos_ver}
%define dpkg_pkg_name dpkg-devel
%else
%define dpkg_pkg_name dpkg
%endif
%endif

%if 0%{?fedora}
%define man_pkg_name man-db
%else
%define man_pkg_name man
%endif

%if 0%{?suse_version}
%define python_pkg_name python-base
%else
%define python_pkg_name python
%endif

%if 0%{?tizen_version:1}
%define rpm_python_pkg_name python-rpm
%else
%define rpm_python_pkg_name rpm-python
%endif

Requires:   %{name}-common = %{version}-%{release}
Requires:   %{dpkg_pkg_name}
Requires:   devscripts
BuildRequires:  python
BuildRequires:  python-setuptools

%if %{with docs}
BuildRequires:  docbook-utils
BuildRequires:  gtk-doc
BuildRequires:  epydoc
%if 0%{?fedora}
BuildRequires:  perl-podlators
%endif
%endif

%if 0%{?do_unittests}
BuildRequires:  python-coverage
BuildRequires:  python-mock
BuildRequires:  python-nose
BuildRequires:  git-core
BuildRequires:  %{man_pkg_name}
BuildRequires:  %{dpkg_pkg_name}
BuildRequires:  devscripts
BuildRequires:  rpm-build
BuildRequires:  %{rpm_python_pkg_name}
BuildRequires:  pristine-tar
BuildRequires:  unzip
BuildRequires:  /usr/bin/zipmerge
BuildRequires:  gnupg
# Missing dep of dpkg in openSUSE
%if 0%{?suse_version}
BuildRequires:  perl-TimeDate
%endif
%endif

%description
Set of tools from Debian that integrate the package build system with Git.
This package contains the original Debian tools.


%package common
Summary:    Common files for git-buildpackage debian and rpm tools
Group:      Development/Tools/Building
Requires:   git-core
Requires:   python-six
Requires:   %{man_pkg_name}
Requires:   %{python_pkg_name}
Requires:   python-setuptools
Requires:   python-dateutil
%if 0%{?centos_ver} && 0%{?centos_ver} <= 7
Requires:       unzip
Requires:       /usr/bin/zipmerge
%else
Recommends:     unzip
Recommends:     /usr/bin/zipmerge
Recommends:     pristine-tar
%endif

%description common
Common files and documentation, used by both git-buildpackage debian and rpm tools


%package rpm
Summary:    Build RPM packages from git
Group:      Development/Tools/Building
Requires:   %{name}-common = %{version}-%{release}
Requires:   rpm
Requires:   %{rpm_python_pkg_name}
%if 0%{?suse_version} || 0%{?tizen_version:1}
Recommends: rpm-build
%else
Requires:   rpm-build
%endif

%description rpm
Set of tools from Debian that integrate the package build system with Git.
This package contains the tools for building RPM packages.

%if %{with docs}
%package doc
Summary:    Documentation for the git-buildpackage suite
Group:      Development/Tools/Building

%description doc
This package contains documentation for the git-buildpackage suite - both the
Debian and the RPM tool set.
%endif


%prep
%setup -q -n %{name}-%{version}



%build
WITHOUT_NOSETESTS=1 %{__python} ./setup.py build

%if %{with docs}
# Prepare apidocs
epydoc -n git-buildpackage --no-sourcecode -o docs/apidocs/ \
    gbp*.py git*.py gbp/

# HTML docs
HAVE_SGML2X=0 make -C docs/
%endif


%if 0%{?do_unittests}
%check
GIT_CEILING_DIRECTORIES=%{_builddir} \
    GIT_AUTHOR_EMAIL=rpmbuild@example.com GIT_AUTHOR_NAME=rpmbuild \
    GIT_COMMITTER_NAME=$GIT_AUTHOR_NAME GIT_COMMITTER_EMAIL=$GIT_AUTHOR_EMAIL \
    %{__python} setup.py nosetests
%endif


%install
rm -rf %{buildroot}
WITHOUT_NOSETESTS=1 %{__python} ./setup.py install --root=%{buildroot} --prefix=/usr
mkdir -p %{buildroot}/usr/share/%{name}
mv %{buildroot}/usr/bin/gbp-builder-mock %{buildroot}/usr/share/%{name}/
mkdir -p %{buildroot}/%{_sysconfdir}/git-buildpackage/
mv %{buildroot}/usr/share/%{name}/gbp.conf %{buildroot}/%{_sysconfdir}/git-buildpackage/

%if %{with docs}
# Install man pages
install -d  %{buildroot}%{_mandir}/man1 %{buildroot}%{_mandir}/man5
install docs/*.1 %{buildroot}%{_mandir}/man1/
install docs/*.5 %{buildroot}%{_mandir}/man5/

# Install html documentation
mkdir -p %{buildroot}%{_docdir}/%{name}
cp -r docs/manual-html %{buildroot}%{_docdir}/%{name}
cp -r docs/apidocs %{buildroot}%{_docdir}/%{name}
%endif

cat > files.list << EOF
%{_bindir}/git-pbuilder
%{python_sitelib}/gbp/deb
%{python_sitelib}/gbp/scripts/pq.py*
%{python_sitelib}/gbp/scripts/buildpackage.py*
%{python_sitelib}/gbp/scripts/dch.py*
%{python_sitelib}/gbp/scripts/import_dsc.py*
%{python_sitelib}/gbp/scripts/import_dscs.py*
%{python_sitelib}/gbp/scripts/import_orig.py*
%{python_sitelib}/gbp/scripts/create_remote_repo.py*
EOF

%if %{with docs}
cat >> files.list << EOF
%{_mandir}/man1/gbp-buildpackage.1*
%{_mandir}/man1/gbp-create-remote-repo.1*
%{_mandir}/man1/gbp-dch.1*
%{_mandir}/man1/gbp-import-dsc.1*
%{_mandir}/man1/gbp-import-dscs.1*
%{_mandir}/man1/gbp-import-orig.1*
%{_mandir}/man1/gbp-pq.1*
%{_mandir}/man1/git-pbuilder.1*
EOF
%endif

# Disable the Debian tools for old CentOS
%if 0%{?centos_ver} && 0%{?centos_ver} < 7
for f in `cat files.list`; do
    rm -rfv %{buildroot}/$f
done

%else

%files -f files.list
%defattr(-,root,root,-)
%endif

%files common
%defattr(-,root,root,-)
%{_bindir}/gbp
%dir %{python_sitelib}/gbp
%dir %{python_sitelib}/gbp/git
%dir %{python_sitelib}/gbp/pkg
%dir %{python_sitelib}/gbp/scripts
%dir %{python_sitelib}/gbp/scripts/common
%{python_sitelib}/gbp-*
%{python_sitelib}/gbp/*.py*
%{python_sitelib}/gbp/scripts/__init__.py*
%{python_sitelib}/gbp/scripts/clone.py*
%{python_sitelib}/gbp/scripts/config.py*
%{python_sitelib}/gbp/scripts/pull.py*
%{python_sitelib}/gbp/scripts/supercommand.py*
%{python_sitelib}/gbp/scripts/common/*.py*
%{python_sitelib}/gbp/git/*.py*
%{python_sitelib}/gbp/pkg/*.py*
%config %{_sysconfdir}/git-buildpackage
%if %{with docs}
%{_mandir}/man1/gbp.1*
%{_mandir}/man1/gbp-clone.1*
%{_mandir}/man1/gbp-config.1*
%{_mandir}/man1/gbp-pull.1*
%{_mandir}/man5/*.5*
%endif


%files rpm
%defattr(-,root,root,-)
%dir %{python_sitelib}/gbp/rpm
%{python_sitelib}/gbp/scripts/*rpm*.py*
%{python_sitelib}/gbp/rpm/*py*
/usr/share/git-buildpackage/gbp-builder-mock
%if %{with docs}
%{_mandir}/man1/gbp-buildpackage-rpm.1*
%{_mandir}/man1/gbp-pq-rpm.1*
%{_mandir}/man1/gbp-import-srpm.1*
%{_mandir}/man1/gbp-rpm-ch.1*
%endif


%if %{with docs}
%files doc
%defattr(-,root,root,-)
%{_docdir}/%{name}/
%endif
