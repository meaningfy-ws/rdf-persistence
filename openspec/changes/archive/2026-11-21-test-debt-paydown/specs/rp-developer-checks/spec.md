<!-- Capability: rp-developer-checks. Change: test-debt-paydown (PD-11: the root-level unit tests
     move to tests/unit/tooling/ and tests/unit/package/). -->

## MODIFIED Requirements

### Requirement: The tests of the changed files run on their own

`make test-changed` SHALL run, without coverage, the unit and feature test folders that match the
files changed against the merge base with `develop` (committed, uncommitted and untracked), slow
tests in them included. A file of `rdf_persistence/<theme>/` SHALL select `tests/unit/<theme>/`, and
a test under a folder of `tests/unit/` that folder. A change in the `core` theme, which every other
theme imports, to shared test infrastructure, or to a file no rule maps, SHALL run `make test-fast`
instead. A change in a file of `rdf_persistence/` that is in no theme and not in the testkit SHALL
select `tests/unit/package/` only. Selected folders SHALL run in parallel; a selection
of test files alone SHALL run on one process. Container tests SHALL NOT run; a changed container test
SHALL be named with the hint `make test-containers`.

#### Scenario: a change in one layer
- **GIVEN** a branch whose only change against `develop` is in `rdf_persistence/persistence/services/`
- **WHEN** `make test-changed` runs
- **THEN** pytest runs `tests/unit/persistence/`, its slow tests included, and no other folder

#### Scenario: a change in the core theme
- **GIVEN** a branch whose only change against `develop` is in `rdf_persistence/core/domain/`
- **WHEN** `make test-changed` runs
- **THEN** it runs `make test-fast` and says that `core` is imported by every theme

#### Scenario: a change outside a theme
- **GIVEN** a branch whose only change against `develop` is `rdf_persistence/__init__.py`
- **WHEN** `make test-changed` runs
- **THEN** pytest runs `tests/unit/package/` and no theme folder

#### Scenario: a changed test file
- **GIVEN** an edited `tests/unit/tenancy/test_tenancy_stores.py` and nothing else
- **WHEN** `make test-changed` runs
- **THEN** pytest runs `tests/unit/tenancy/`, in parallel

#### Scenario: a changed root-level test file
- **GIVEN** an edited test file directly in `tests/unit/` (none is left there by this change; a new
  one) and nothing else
- **WHEN** `make test-changed` runs
- **THEN** pytest runs that file only, on one process

#### Scenario: a changed tooling test file
- **GIVEN** an edited `tests/unit/tooling/test_markers.py` and nothing else
- **WHEN** `make test-changed` runs
- **THEN** pytest runs `tests/unit/tooling/`, in parallel

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
