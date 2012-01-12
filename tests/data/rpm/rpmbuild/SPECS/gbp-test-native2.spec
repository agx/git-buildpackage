Name:       gbp-test-native2
Summary:    Test package for git-buildpackage
Version:    2.0
Release:    0
Group:      Development/Libraries
License:    GPLv2
Source:     foo.txt
BuildRequires:  unzip

%description
Package for testing the RPM functionality of git-buildpackage.
Mimics a "native" package that doesn't have any source tarball.


%prep
# Just create build dir
%setup -T -c
cp %{SOURCE0} .


%build
# Nothing to do


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/%{_datadir}/%{name}
cp -R * %{buildroot}/%{_datadir}/%{name}



%files
%defattr(-,root,root,-)
%dir %{_datadir}/%{name}
%{_datadir}/%{name}
