#!/usr/bin/make

MAN1S = \
        gbp               \
        gbp-buildpackage  \
        gbp-clone         \
        gbp-config        \
        gbp-create-remote-repo \
        gbp-dch           \
        gbp-import-dsc    \
        gbp-import-dscs   \
        gbp-import-orig   \
        gbp-pq            \
        gbp-pull          \
        gbp-buildpackage-rpm \
        gbp-import-srpm   \
        gbp-pq-rpm        \
        gbp-rpm-ch        \
        $(NULL)

MAN5S = gbp.conf

MANUAL=manual-html
SGML_MANPAGES=$(patsubst %,%.1,$(MAN1S)) $(patsubst %,%.5,$(MAN5S))
POD_MANPAGES=git-pbuilder.1
MANPAGES=$(SGML_MANPAGES) $(POD_MANPAGES)
VERSION_ENT=version.ent
GBP_VERSION=../gbp/version.py
DEB_VERSION=$(shell sed -ne 's/^gbp_version\s\+=\s\+"\([.a-z0-9~-]\+\)"/\1/p' $(GBP_VERSION))
CHANGELOG=../debian/changelog
MAN_DATE=$(shell dpkg-parsechangelog -l ../debian/changelog -SDate | TZ=UTC LC_ALL=C date -f- +'%d %B %Y')

# Stuff to build docs outside Debian
HAVE_SGML2X ?= 1
GTK_DOC_CATALOG_FILE ?= /usr/share/sgml/gtk-doc/gtk-doc.cat

all: $(MANUAL) $(MANPAGES)

$(MANUAL): manual.sgml chapters/*.sgml manpages/*.sgml common.ent $(VERSION_ENT)
ifeq ($(HAVE_SGML2X),1)
	docbook-2-html -s local $<
else
	docbook2html -d local-nosgml2x.dsl -c $(GTK_DOC_CATALOG_FILE) -o $(MANUAL) $<
endif
	sed -i 's/^CLASS="[A-Z0-9]\+"/\L&/' manual-html/*.html
	cp /usr/share/gtk-doc/data/*.png $(MANUAL)

# We build manpages under 'buildxref/' just to get an updated cross-reference
# file (manpage.refs), before building the final manpages
BUILD_MAN_XREF_PAGES=$(patsubst %,buildxref/%,$(SGML_MANPAGES))

buildxref/%.1 buildxref/%.5: man.%.sgml manpages/%.sgml
	docbook2man -o buildxref $<
	sed -i -r "s/\"[^\"]+\"/\"$(MAN_DATE)\"/3" $@

manpage.refs: $(BUILD_MAN_XREF_PAGES)
	cp buildxref/$@ $@

%.1 %.5: manpage.refs
	docbook2man -o . man.$*.sgml
	sed -i -r "s/\"[^\"]+\"/\"$(MAN_DATE)\"/3" $@

git-pbuilder.1: ../bin/git-pbuilder
	pod2man $< $@

manual.sgml: $(VERSION_ENT)

$(VERSION_ENT): $(GBP_VERSION)
	echo '<!ENTITY gbp-version "$(DEB_VERSION)">' > $(VERSION_ENT)

clean:
	-rm -r manual-html/
	-rm *.1 *.5 manpage.* $(VERSION_ENT)
	-rm -r buildxref

