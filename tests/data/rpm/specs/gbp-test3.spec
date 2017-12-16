Name:       gbp-test3
Summary:    Test package 3 for git-buildpackage
Version:    1.0
Release:    0
Group:      Development/Libraries
License:    GPLv2
Source:     %{name}-%{version}.tar.gz
# Gbp-Ignore-Patches: 10
Patch:      my.patch
Patch10:    my2.patch
Patch20:    my3.patch

%description
Another test package for git-buildpackage.


%prep
%autosetup -n %{name}-%{version}


%build
make


%install
mkdir -p %{buildroot}/%{_datadir}/%{name}


%files
%defattr(-,root,root,-)
%dir %{_datadir}/%{name}
%{_datadir}/%{name}
