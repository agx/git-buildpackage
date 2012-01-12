Name:       gbp-test2
Summary:    Test package 2 for git-buildpackage
Epoch:      2
Version:    3.0
Release:    0
Group:      Development/Libraries
License:    GPLv2
Source10:   ftp://ftp.host.com/%{name}-%{version}.tar.gz
Source:     foo.txt
Source20:   bar.tar.gz
# Gbp-Ignore-Patches: -1
Patch:      my.patch
Patch10:    my2.patch
Patch20:    my3.patch
Packager:   Markus Lehtonen <markus.lehtonen@linux.intel.com>
VCS:        myoldvcstag

%description
Package for testing the RPM functionality of git-buildpackage.

%package empty
Summary:    Empty subpackage

%description empty
Empty subpackage for the %{name} test package.


%prep
%setup -T -n %{name}-%{version} -c -a 10

%patch
%patch -P 10 -p1

echo "Do things"

# Gbp-Patch-Macros

%build
make


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/%{_datadir}/%{name}
cp -R * %{buildroot}/%{_datadir}/%{name}
install %{SOURCE0} %{buildroot}/%{_datadir}/%{name}


%changelog
* Tue Feb 04 2014 Name <email> 1
- My change


%files
%defattr(-,root,root,-)
%dir %{_datadir}/%{name}
%{_datadir}/%{name}

%files empty
%defattr(-,root,root,-)
