#
# Spec file for testing all RPM tags (that we know of
#

%define suse_release %(test -e /etc/SuSE-release && head -n1 /etc/SuSE-release | cut -d ' ' -f2 | cut --output-delimiter=0 -d. -f1,2 || echo 0)
%if "%{suse_release}" >= "1201"
%define test_weak_dep_tags 1
%if "%{suse_release}" < "1302"
%define test_weak_dep_tags_2 1
%endif
%endif

%define test_arch_os_tags %(test -n "$GBP_SKIP_ARCH_OS_TAGS" && echo 0 || echo 1)

%define source_fn_base source
%define patch_fn_base patch

# Gbp-Undefined-Tag: foobar

# Test that we accept different cases
NAME:           my_name
version:        0
ReLeasE:        0

# Rest of the tags
Epoch:          0
Summary:        my_summary
License:        my_license
Distribution:   my_distribution
Vendor:         my_vendor
Group:          my_group
Packager:       my_packager
Url:            my_url
Vcs:            my_vcs
Source:         my_source
Patch:          my_%patch_fn_base
Patch0:         my_%{patch_fn_base}0
Nosource:       0
Nopatch:        0
#Icon:           my_icon
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

%if 0%{?test_weak_dep_tags}
Recommends:     my_recommends
Suggests:       my_suggests
Supplements:    my_supplements
Enhances:       my_enhances
%if 0%{?test_weak_dep_tags_2}
BuildRecommends:my_buildrecommends
BuildSuggests:  my_buildsuggests
BuildSupplements:my_buildsupplements
BuildEnhances:  my_buildenhances
%endif
%endif

# These should be filtered out by GBP
%if "%{test_arch_os_tags}" != "0"
BuildArch:      my_buildarch
ExcludeArch:    my_excludearch
ExclusiveArch:  my_exclusivearch
ExcludeOs:      my_excludeos
ExclusiveOs:    my_exclusiveos
%endif

%description
Package for testing GBP.

