Running the Tests
-----------------

The tests are run via

```sh
make
```

To also run the component tests, you need to initialize the git submodules once
via:

```sh
git submodule update --init --recursive
```

This will fetch the necessary binary data for the DEB and RPM component tests,
and the tests are from now on included within each regular test run.

Some tests reach out to the network. To run these in addition to all
other tests use:

```sh
make all+net
```

You can run the tests in a `debian:sid` docker container by using

```sh
packaging/run-in-container
```

The python tests use `pytest` so you can use all it's options. To run a
single test e.g.

```sh
pytest tests/component/deb/test_push.py::TestPush::test_push_failure
```

If you want to keep any temporary repos around for inspection use
`GBP_TESTS_NOCLEAN`:

```sh
GBP_TESTS_NOCLEAN=1 pytest tests/component/deb/test_push.py::TestPush::test_push_failure
```

Building the API Docs
---------------------

You can build the API docs using

```sh
make apidocs
```

Contributing Patches
--------------------

Make sure the tests pass before sending in patch. You can either send
it to the mailing list, add it to a bug report against
git-buildpackage on <http://bugs.debian.org/src:git-buildpackage> or
open a merge request at
<https://salsa.debian.org/agx/git-buildpackage/-/merge_requests>

Please add a `Signed-off-by:` to commit messages to indicate that you agree to
the [Developer's Certificate of Origin][].

If you fix a regression or add a new feature please make sure this is covered
by either a unittest (`tests/*.py`) or a component test that exercises one of the
scripts (`tests/component/{deb,rpm}/*.py`).

Layout
------

    gbp/scripts/*.py    - the actual gbp commands (buildpackage, dch, …)
    gbp/scripts/common/ - code shared between Debian and RPM commands
    gbp/deb/            - Debian package handling (control, dsc, …)
    gbp/rpm/            - RPM package handling (spec files, …)
    gbp/git/            - Git repository interaction
    tests/*.py          - unit tests
    tests/doctests      - doctests that also serve as examples
    tests/component/    - component tests that invoke actual commands

Interfaces
----------

A gbp command in `gbp/scripts/<command>.py` must provide these interfaces:

When one invokes `gbp <command>` `gbp/scripts/<command>.py` is imported by

    gbp/scripts/supercommand.py

which then invokes it's *main* function with all given command line arguments.
It is expected to return with the exit status that should be passed back to the
shell.

When one invokes `gbp config <command>` `gbp/scripts/<command>.py` is imported by

    gbp/scripts/config.py

which then invokes it's *build_parser* function with the command name as argument.
It is expected to return a `GbpConfigParser` with all config files parsed.

[Developer's Certificate of Origin]: https://developercertificate.org/
