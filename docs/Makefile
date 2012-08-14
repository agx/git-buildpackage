#!/usr/bin/make

MAN1S = git-buildpackage  \
        git-import-dsc    \
        git-import-dscs   \
        git-import-orig   \
        git-dch           \
        gbp-pull          \
        gbp-clone         \
        gbp-pq            \
        gbp-create-remote-repo
MAN5S = gbp.conf

MANUAL=manual-html
SGML_MANPAGES=$(patsubst %,%.1,$(MAN1S)) $(patsubst %,%.5,$(MAN5S))
POD_MANPAGES=git-pbuilder.1
MANPAGES=$(SGML_MANPAGES) $(POD_MANPAGES)
VERSION_ENT=version.ent
GBP_VERSION=../gbp/version.py
DEB_VERSION=$(shell sed -ne 's/^gbp_version="\([.a-z0-9~]\+\)"/\1/p' $(GBP_VERSION))
CHANGELOG=../debian/changelog

all: $(MANUAL) $(MANPAGES)

$(MANUAL): manual.sgml chapters/*.sgml manpages/*.sgml
	docbook-2-html -s local $<
	cp /usr/share/gtk-doc/data/*.png $(MANUAL)

# We build manpages under 'buildxref/' just to get an updated cross-reference
# file (manpage.refs), before building the final manpages
BUILD_MAN_XREF_PAGES=$(patsubst %,buildxref/%,$(SGML_MANPAGES))

buildxref/%.1 buildxref/%.5: man.%.sgml manpages/%.sgml
	docbook2man -o buildxref $<

manpage.refs: $(BUILD_MAN_XREF_PAGES)
	cp buildxref/$@ $@

%.1 %.5: manpage.refs
	docbook2man -o . man.$*.sgml

git-pbuilder.1: ../bin/git-pbuilder
	pod2man $< $@

manual.sgml: $(VERSION_ENT)

$(VERSION_ENT): $(GBP_VERSION)
	echo '<!ENTITY gbp-version "$(DEB_VERSION)">' > $(VERSION_ENT)

clean:
	-rm -r manual-html/
	-rm *.1 *.5 manpage.* $(VERSION_ENT)
	-rm -r buildxref

