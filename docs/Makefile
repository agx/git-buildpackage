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
        gbp-import-ref    \
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

MAN5S = \
	gbp.conf \
	$(NULL)

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

# Select docbook-to-man tool
ifeq ($(shell which docbook2x-man), )
	DOCBOOK_TO_MAN=docbook-to-man
else
	DOCBOOK_TO_MAN=docbook2x-man
endif

all: manual $(MANPAGES)

manual: $(MANUAL)/index.html $(DEST_IMAGES) css

$(MANUAL)/index.html: manual.xml chapters/*.xml manpages/*.xml common.ent $(VERSION_ENT)
	mkdir -p $(MANUAL)
	xsltproc -o $(MANUAL)/ /usr/share/gtk-doc/data/gtk-doc.xsl $<
	cp /usr/share/gtk-doc/data/*.png \
	   /usr/share/gtk-doc/data/*.css \
	   $(MANUAL)

$(MANUAL)/gbp.pdf: manual.xml chapters/*.xml manpages/*.xml common.ent $(VERSION_ENT)
	xsltproc -o $(MANUAL)/ /usr/share/gtk-doc/data/gtk-doc.xsl $<

css: $(MANUAL)/gbp.css $(MANUAL)/gbp.svg
$(MANUAL)/gbp.css $(MANUAL)/gbp.svg: gbp.css gbp.svg
	cp gbp.css gbp.svg $(MANUAL)/

html_images: $(DEST_IMAGES)
$(MANUAL)/images/%.png: images/%.png
	mkdir -p $(basename $@)
	install $< $@

%.1 %.5: man.gbp.xml manpages/%.xml
	$(DOCBOOK_TO_MAN) -o . $<

git-pbuilder.1: ../bin/git-pbuilder
	pod2man $< $@

manual.xml: $(VERSION_ENT)

$(GBP_VERSION): ../debian/changelog
	cd .. && python setup.py build --help >/dev/null

$(VERSION_ENT): $(GBP_VERSION)
	echo '<!ENTITY gbp-version "$(DEB_VERSION)">' > $(VERSION_ENT)

clean:
	-rm -r $(MANUAL)
	-rm *.1 *.5 $(VERSION_ENT)
