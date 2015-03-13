Name:       gbp-test-native
Summary:    Test package for git-buildpackage
Version:    1.0
Release:    1
Group:      Development/Libraries
License:    GPLv2
Source1:    %{name}-%{version}.zip
BuildRequires:  unzip

%description
Package for testing the RPM functionality of git-buildpackage.
Mimics a "native" package


%prep
unzip %{SOURCE1}
%setup -T -D


%build
make


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/%{_datadir}/%{name}
cp -R * %{buildroot}/%{_datadir}/%{name}



%files
%defattr(-,root,root,-)
%dir %{_datadir}/%{name}
%{_datadir}/%{name}
