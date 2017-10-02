#!/usr/bin/make

MAN1S = \
        gbp               \
        gbp-buildpackage  \
        gbp-clone         \
        gbp-config        \
        gbp-create-remote-repo \
        gbp-dch           \
        gbp-export-orig   \
        gbp-import-dsc    \
        gbp-import-dscs   \
        gbp-import-orig   \
        gbp-pq            \
        gbp-pristine-tar  \
        gbp-pull          \
        gbp-push          \
        gbp-tag           \
        gbp-buildpackage-rpm \
        gbp-import-srpm   \
        gbp-pq-rpm        \
        gbp-rpm-ch        \
        $(NULL)

MAN5S = gbp.conf

MANUAL=manual-html
XML_MANPAGES=$(patsubst %,%.1,$(MAN1S)) $(patsubst %,%.5,$(MAN5S))
POD_MANPAGES=git-pbuilder.1
MANPAGES=$(XML_MANPAGES) $(POD_MANPAGES)
VERSION_ENT=version.ent
GBP_VERSION=../gbp/version.py
DEB_VERSION=$(shell sed -ne 's/^gbp_version\s\+=\s\+"\([.a-z0-9~-]\+\)"/\1/p' $(GBP_VERSION))
CHANGELOG=../debian/changelog
MAN_DATE=$(shell dpkg-parsechangelog -l ../debian/changelog -SDate | TZ=UTC LC_ALL=C date -f- +'%d %B %Y')
IMAGES=$(wildcard images/*png)
DEST_IMAGES=$(subst images/,$(MANUAL)/images/,$(IMAGES))

# Stuff to build docs outside Debian
HAVE_XML2X ?= 1
GTK_DOC_CATALOG_FILE ?= /usr/share/xml/gtk-doc/gtk-doc.cat

all: manual $(MANPAGES)

manual: $(MANUAL) html_images css

$(MANUAL): manual.xml chapters/*.xml manpages/*.xml common.ent $(VERSION_ENT)
ifeq ($(HAVE_XML2X),1)
	docbook-2-html -s local $<
else
	docbook2html -d local-noxml2x.dsl -c $(GTK_DOC_CATALOG_FILE) -o $(MANUAL) $<
endif
	sed -i 's/^CLASS="[A-Z0-9]\+"/\L&/' manual-html/*.html
	cp /usr/share/gtk-doc/data/*.png $(MANUAL)

css: gbp.css gbp.svg
	cp gbp.css gbp.svg $(MANUAL)

html_images: $(DEST_IMAGES)
$(MANUAL)/images/%.png: images/%.png
	mkdir -p -p $(basename $@)
	install $< $@

# We build manpages under 'buildxref/' just to get an updated cross-reference
# file (manpage.refs), before building the final manpages
BUILD_MAN_XREF_PAGES=$(patsubst %,buildxref/%,$(XML_MANPAGES))

buildxref/%.1 buildxref/%.5: man.%.xml manpages/%.xml
	docbook2x-man -o buildxref $<
	sed -i -r "s/\"[^\"]+\"/\"$(MAN_DATE)\"/3" $@

manpage.refs: $(BUILD_MAN_XREF_PAGES)
	cp buildxref/$@ $@

%.1 %.5: manpage.refs
	docbook2x-man -o . man.$*.xml
	sed -i -r "s/\"[^\"]+\"/\"$(MAN_DATE)\"/3" $@

git-pbuilder.1: ../bin/git-pbuilder
	pod2man $< $@

manual.sgml: $(VERSION_ENT)

$(GBP_VERSION): ../debian/changelog
	cd .. && python setup.py build --help >/dev/null

$(VERSION_ENT): $(GBP_VERSION)
	echo '<!ENTITY gbp-version "$(DEB_VERSION)">' > $(VERSION_ENT)

clean:
	-rm -r manual-html/
	-rm *.1 *.5 manpage.* $(VERSION_ENT)
	-rm -r buildxref
