#
# Spec for testing some quirks of spec parsing
#

Name:           pkg_name
Summary:        Spec for testing some quirks of spec parsing
Version:        0.1
Release:        1.2
License:        GPLv2
Source1:        foobar.tar.gz
# Gbp-Ignore-Patches: 2 4 888
Patch1:         01.patch
Patch2:         02.patch
Patch3:         03.patch
Patch4:         04.patch
Patch5:         05.patch

%description
Spec for testing some quirks of spec parsing. No intended for building an RPM.

%prep
# We don't have Source0 so rpmbuild would fail, but gbp shouldn't crash
%setup -q

# Patches are applied out-of-order wrt. numbering
%patch5
%patch2
%patch1 -F2
# Patch 999 does not exist, rpmbuild would fail but GBP should not
%patch999
