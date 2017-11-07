PY_EXAMPLES=$(shell grep -l /usr/bin/python examples/*)
FLAKE_OPTS=$(shell test -w /dev/shm || echo '-j1')
NOSE_OPTS=--with-xcoverage
TEST_LOCALE?=C.UTF-8

all: syntax-check test

all+net:
	$(MAKE) GBP_NETWORK_TESTS=1 all

test:
	export GIT_AUTHOR_NAME="Gbp Tests";		\
	export GIT_AUTHOR_EMAIL=tests@example.com;	\
	export GIT_COMMITTER_NAME=$$GIT_AUTHOR_NAME;	\
	export GIT_COMMITTER_EMAIL=$$GIT_AUTHOR_EMAIL;	\
	PYTHONPATH=.					\
	LC_ALL=$(TEST_LOCALE) python3 setup.py nosetests $(NOSE_OPTS)

syntax-check:
	flake8 $(FLAKE_OPTS)
	flake8 $(FLAKE_OPTS) $(PY_EXAMPLES)

docs:
	$(MAKE) -C docs
	$(MAKE) apidocs

apidocs:
	mkdir -p build
	pydoctor -v --config=.pydoctor.cfg

.PHONY: docs
