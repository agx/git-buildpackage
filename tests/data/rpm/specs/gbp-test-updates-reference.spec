#
# Spec file for testing deleting/adding/updating tags and macros
#

# Gbp-Undefined-Tag: foobar

# Test that we accept different cases
Name:           my_name
Version:        0
Release:        1
Summary:        my_summary
License:        new license
Distribution:   my_distribution
Group:          my_group
Packager:       my_packager
Url:            my_url
Vcs:            my_vcs
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

%patch0 my new args

%build

%install
