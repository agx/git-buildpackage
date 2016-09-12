all: syntax-check test

test:
	export GIT_AUTHOR_NAME="Gbp Tests";		\
	export GIT_AUTHOR_EMAIL=tests@example.com;	\
	export GIT_COMMITTER_NAME=$$GIT_AUTHOR_NAME;	\
	export GIT_COMMITTER_EMAIL=$$GIT_AUTHOR_EMAIL;	\
	PYTHONPATH=.					\
	python setup.py nosetests --with-xcoverage

syntax-check:
	PYTHONPATH=. pychecker $(PYCHECKER_ARGS) -q \
	    gbp gbp.scripts gbp.git gbp.deb

docs:
	make -C docs

apidocs:
	mkdir -p build
	epydoc -v --config=setup.cfg

.PHONY: docs
