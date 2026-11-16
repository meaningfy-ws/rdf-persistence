## ADDED Requirements

### Requirement: A test cannot hang the checks

Every pytest run SHALL stop a test that runs longer than 120 s and name it, and every CI job
SHALL stop after 30 minutes.

#### Scenario: a test that never returns
- **GIVEN** a unit test that awaits an event nobody sets
- **WHEN** `make test` runs
- **THEN** the test fails after 120 s naming itself, and the other tests still run

### Requirement: A flaky test is quarantined, not retried

A test that passes and fails on unchanged code SHALL carry the `quarantine` marker with an issue
link; the unit and feature lanes SHALL leave quarantined tests out, and no lane SHALL retry a
failed test.

#### Scenario: a quarantined test
- **GIVEN** a test marked `quarantine` with an issue link
- **WHEN** `make test` runs
- **THEN** the test does not run and the lane does not fail on it

### Requirement: Property-based tests are derandomised in CI on every worker

The Hypothesis profiles SHALL be registered and loaded once, in `tests/conftest.py`; with `CI`
set, every `@given` test SHALL run the derandomised `ci` profile on every xdist worker.

#### Scenario: a property test on any worker
- **GIVEN** `CI` is set and `make test` runs on several workers
- **WHEN** `test_sparql.py::test_any_string_literal_round_trips` runs on any worker
- **THEN** it draws the same examples on every run

### Requirement: Mutation testing runs on demand

`make mutation` SHALL run mutmut with the selection in `setup.cfg` (by default the `domain`
layer and its unit tests) and print its results; it SHALL NOT be part of `make check-all` or CI.

#### Scenario: the domain layer
- **WHEN** `make mutation` runs with the default selection
- **THEN** it reports killed, survived and untested mutants of `domain/`, generated code excluded
