PYTHON=python3
PY_EXAMPLES=$(shell grep -l /usr/bin/python examples/*)
FLAKE_OPTS=$(shell test -w /dev/shm || echo '-j1')
TEST_LOCALE?=C.UTF-8

SH_SCRIPTS = \
  packaging/run-in-container \
  $(NULL)

all: syntax-check test

all+net:
	GBP_NETWORK_TESTS=1 $(MAKE) all

test:
	export HOME=/nonexisting;                       \
	export GIT_AUTHOR_NAME="Gbp Tests";		\
	export GIT_AUTHOR_EMAIL=tests@example.com;	\
	export GIT_COMMITTER_NAME=$$GIT_AUTHOR_NAME;	\
	export GIT_COMMITTER_EMAIL=$$GIT_AUTHOR_EMAIL;	\
	export DEBEMAIL=$$GIT_AUTHOR_EMAIL;             \
	PYTHONPATH=.					\
	LC_ALL=$(TEST_LOCALE)                           \
	$(PYTHON) -m pytest $(PYTEST_ARGS)

syntax-check:
	flake8 $(FLAKE_OPTS)
	flake8 $(FLAKE_OPTS) $(PY_EXAMPLES)

type-check:
	mypy $(MYPY_ARGS) gbp

shell-check:
	@echo "# Validating zsh completion"
	zsh debian/zsh/_gbp
	@echo "# Validating bash completion"
	shellcheck --shell=bash debian/git-buildpackage.bash-completion
	shellcheck $(SH_SCRIPTS)

docs:
	$(MAKE) -C docs
	$(MAKE) apidocs

apidocs:
	mkdir -p build

venv: venv/stamp
venv/stamp:
	$(PYTHON) -m venv venv
	. venv/bin/activate && pip install -r dev_requirements.txt
	touch '$@'

.PHONY: docs venv
