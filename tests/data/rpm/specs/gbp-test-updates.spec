#
# Spec file for testing deleting/adding/updating tags and macros
#

# Gbp-Undefined-Tag: foobar

# Test that we accept different cases
Name:           my_name
Version:        0
Release:        1
Summary:        my_summary
License:        my_license
Distribution:   my_distribution
Vendor:         my_vendor
Group:          my_group
Packager:       my_packager
Url:            my_url
Vcs:            my_vcs
Source:         my_source
Patch0:         my_%patch_fn_base
Patch1:         my_%{patch_fn_base}1
Nosource:       0
Nopatch:        0
BuildRoot:      my_buildroot
Provides:       my_provides
Requires:       my_requires
Conflicts:      my_conflicts
Obsoletes:      my_obsoletes
BuildConflicts: my_buildconflicts
BuildRequires:  my_buildrequires
AutoReqProv:    No
AutoReq:        No
AutoProv:       No
DistTag:        my_disttag
BugUrl:         my_bugurl

%description
Package for testing GBP.

%prep
%setup -n my_prefix

%patch -P0 -b my_patch
%patch -P1 -b my_patch1

%build

%install
