<!-- Capability: rp-developer-checks. Change: delivery-friction. -->

## ADDED Requirements

### Requirement: The checks give the same answer on every run

`make check-all` and `make test-containers` SHALL pass or fail for the same commit regardless of
test order, the worker a test runs on, machine load or the availability of Maven Central, and SHALL
fail when a Python file is not formatted. Tests that assert a wall-clock budget SHALL run only in
their own lane (`make test-perf`), outside `make check-all` and CI.

#### Scenario: the listing test in the full suite
- **GIVEN** the full `make test` run, in any order and on any worker
- **WHEN** `test_an_item_is_what_a_read_of_the_same_book_returns` runs
- **THEN** it passes whenever the item and the read of the same book hold the same values, in any
  order of a multivalued slot

#### Scenario: Maven Central refuses a download
- **GIVEN** a CI run whose Fuseki image is in the Actions cache
- **WHEN** the container tests start
- **THEN** Fuseki starts from the cached image, without fetching from `repo1.maven.org`

#### Scenario: an unformatted file
- **GIVEN** a Python file that `ruff format` would change
- **WHEN** `make check-all` runs
- **THEN** it fails naming the file

#### Scenario: a timing budget under load
- **GIVEN** a test that asserts a wall-clock budget
- **WHEN** `make check-all` runs on a loaded machine
- **THEN** the test does not run; `make test-perf` runs it

### Requirement: The unit and feature tests run in parallel

`make test` SHALL run the unit and feature tests on several worker processes (`pytest-xdist`,
`-n auto`) with the same coverage floor as before.

#### Scenario: make test
- **WHEN** `make test` runs
- **THEN** pytest reports several workers, every test passes and coverage is measured over all of them

### Requirement: The testing checklist names only public helpers

`make check-docs` SHALL fail when `develop/testing.adoc` names a `testkit.<name>` that
`rdf_persistence.testkit` does not list in `__all__`.

#### Scenario: a helper the testkit does not export
- **GIVEN** `develop/testing.adoc` names `testkit.some_helper`
- **WHEN** `make check-docs` runs
- **THEN** it fails naming `some_helper`
