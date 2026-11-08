<!-- Capability: rp-developer-checks. Change: delivery-friction. -->

## ADDED Requirements

### Requirement: The checks give the same answer on every run

`make check-all` and `make test-containers` SHALL pass or fail for the same commit regardless of
test order, hash seed, machine load or the availability of Maven Central, and SHALL fail when a
Python file is not formatted.

#### Scenario: the listing test in the full suite
- **GIVEN** the full `make test` run in any order
- **WHEN** `test_an_item_is_what_a_read_of_the_same_book_returns` runs
- **THEN** it passes whenever the item and the read of the same book hold the same statements

#### Scenario: Maven Central refuses a download
- **GIVEN** a CI run whose container job cannot reach `repo1.maven.org`
- **WHEN** the container tests start
- **THEN** Fuseki starts from the cached image or jar

#### Scenario: an unformatted file
- **GIVEN** a Python file that `ruff format` would change
- **WHEN** `make check-all` runs
- **THEN** it fails naming the file

### Requirement: The testing checklist names only public helpers

`make check-docs` SHALL fail when `develop/testing.adoc` names a `testkit.<name>` that
`rdf_persistence.testkit` does not export.

#### Scenario: a helper the testkit does not export
- **GIVEN** `develop/testing.adoc` names `testkit.some_helper`
- **WHEN** `make check-docs` runs
- **THEN** it fails naming `some_helper`
