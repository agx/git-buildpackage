all: syntax-check test

all+net:
	$(MAKE) GBP_NETWORK_TESTS=1 all

test:
	export GIT_AUTHOR_NAME="Gbp Tests";		\
	export GIT_AUTHOR_EMAIL=tests@example.com;	\
	export GIT_COMMITTER_NAME=$$GIT_AUTHOR_NAME;	\
	export GIT_COMMITTER_EMAIL=$$GIT_AUTHOR_EMAIL;	\
	PYTHONPATH=.					\
	python setup.py nosetests --with-xcoverage

syntax-check:
	flake8 -j1

docs:
	make -C docs

apidocs:
	mkdir -p build
	epydoc -v --config=setup.cfg

.PHONY: docs
