## ADDED Requirements

### Requirement: The tests of the changed files run on their own

`make test-changed` SHALL run, without coverage, the unit and feature test folders that match the
files changed against the merge base with `develop` (committed, uncommitted and untracked), slow
tests in them included. A change to shared test infrastructure, or to a file no rule maps, SHALL
run `make test-fast` instead. Container tests SHALL NOT run; a changed container test SHALL be
named with the hint `make test-containers`.

#### Scenario: a change in one layer
- **GIVEN** a branch whose only change against `develop` is in `rdf_persistence/services/`
- **WHEN** `make test-changed` runs
- **THEN** pytest runs `tests/unit/services/`, its slow tests included, and no other folder

#### Scenario: a changed test file
- **GIVEN** an edited `tests/unit/domain/test_exceptions.py` and nothing else
- **WHEN** `make test-changed` runs
- **THEN** pytest runs `tests/unit/domain/`, on one process, because test modules import each other

#### Scenario: a changed root-level test file
- **GIVEN** an edited `tests/unit/test_public_api.py` and nothing else
- **WHEN** `make test-changed` runs
- **THEN** pytest runs that file only, on one process

#### Scenario: a change to shared test infrastructure
- **GIVEN** an edited `tests/conftest.py`, `pytest.ini`, `pyproject.toml`, `uv.lock`, `Makefile`,
  `tests/toy_service.py`, a schema under `rdf_persistence/model/` or `tests/e2e/library_app.py`
- **WHEN** `make test-changed` runs
- **THEN** it runs `make test-fast` and says why

#### Scenario: a changed container test
- **GIVEN** an edited `tests/integration/store/test_fuseki_store.py` and nothing else
- **WHEN** `make test-changed` runs
- **THEN** it runs no test and names the file with the hint `make test-containers`

#### Scenario: nothing changed
- **GIVEN** a branch equal to its merge base with `develop` and a clean working tree
- **WHEN** `make test-changed` runs
- **THEN** it runs no test, says that there is nothing to run, and exits 0

### Requirement: The fast lane leaves out slow tests

`make test-fast` SHALL run every unit and feature test not marked `slow`, in parallel, without
coverage. A test that takes seconds on its own, because it runs a tool, a subprocess or a whole
generation, SHALL carry `@pytest.mark.slow`. `make check-all`, `make test`, `make test-unit`,
`make test-feature` and CI SHALL run slow tests too, with their coverage floors unchanged.

#### Scenario: the fast lane
- **WHEN** `make test-fast` runs
- **THEN** no test marked `slow` runs, every other unit and feature test runs, and no coverage is
  measured

#### Scenario: the stage gate
- **WHEN** `make check-all` runs
- **THEN** the tests marked `slow` run, and the 80 % coverage floor applies as before

### Requirement: Check timings come from a repeatable profile

`make profile-tests` SHALL run the unit and feature tests without coverage and print the 15 slowest
tests with set-up and call times apart; `PROFILE_MARK` SHALL narrow the selection (a pytest `-m`
expression, default `unit or feature`). The timings table in `develop/index.adoc` SHALL give, for
`make check-all`, `make test-containers`, `make test-fast` and `make test-changed`, a measured time
with its date, and SHALL name the slowest tests.

#### Scenario: a developer refreshes the table
- **WHEN** a developer runs `make profile-tests` on the current `develop`
- **THEN** it prints the total time and the 15 slowest tests, set-up and call apart

#### Scenario: an unmarked slow test
- **GIVEN** a new test that takes 20 s and carries no `slow` mark
- **WHEN** a developer runs `make profile-tests PROFILE_MARK="(unit or feature) and not slow"`
- **THEN** the test is listed among the 15 slowest, so it can be marked
