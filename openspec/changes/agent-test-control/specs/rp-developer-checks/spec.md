## ADDED Requirements

### Requirement: Heavy test runs queue on the machine

Every make target that runs a parallel test lane, `make test-containers` and `make test-seed` SHALL
run its pytest command behind one lock shared by every repository on the machine, so that one
such run executes at a time. A run that waits SHALL say once whose run holds the lock (folder,
command, process, start time), and, when it starts, how long it waited. The lock SHALL be released when the run ends, however it ends.
A named-file run (`uv run pytest <file>`) and `make test-changed`'s own runs SHALL NOT take the lock.

#### Scenario: two sessions start a lane
- **GIVEN** a session running `make test-fast` in one repository
- **WHEN** another session starts `make check-all` in another repository on the same machine
- **THEN** the second prints `waiting for the test queue:` with the first run's folder and its
  target `test-fast`,
  and its first lane starts only after the first run ends

#### Scenario: a run is killed
- **GIVEN** a queued run that holds the lock
- **WHEN** its process is killed
- **THEN** the next waiting run starts without any manual clean-up

#### Scenario: a narrow run
- **GIVEN** a queued run that holds the lock
- **WHEN** a builder runs `make test-changed` or `uv run pytest <file>`
- **THEN** it runs at once

### Requirement: The lead seeds the test selection of a worktree

`make test-seed` SHALL run every unit and feature test of the worktree, slow tests included,
without coverage, and record which code each test executed (pytest-testmon). The recorded data
SHALL replace the previous data only when the run completed (pytest exit 0 or 1), in one step, so
that a reader never sees partial data.

#### Scenario: the seed completes with a failing test
- **WHEN** `make test-seed` runs and one test fails
- **THEN** the selection data is replaced, and the failing test is selected by the next
  `make test-changed`

#### Scenario: the seed is interrupted
- **GIVEN** selection data from an earlier seed
- **WHEN** `make test-seed` is interrupted
- **THEN** the earlier data stays and the target fails

### Requirement: A test worker releases memory between test modules

After every test, a test process SHALL clear the caches of linkml-runtime's `SchemaView` and of
FastAPI's dependency models; when it moves from one test module to the next, and after its last
test, it SHALL also collect garbage and return freed memory to the system where the platform
allows. `TEST_RELEASE=off`
SHALL turn the release off.

#### Scenario: the feature tests on one process (@manual, measured by the lead in task 1.3)
- **WHEN** the feature tests not marked slow run on one process
- **THEN** its maximum resident memory stays under 600 MB

#### Scenario: one module that builds a service per test (@manual, measured by the lead in task 1.3)
- **WHEN** `tests/unit/api/test_allowed_actions_adversarial.py` runs on one process
- **THEN** its memory does not grow with the number of tests it has run (about 35 MB per test
  before)

#### Scenario: apps no test holds
- **GIVEN** three service apps built and dropped by a test module
- **WHEN** the process moves to the next module
- **THEN** none of their service kits is still in memory

#### Scenario: a library drops its caches
- **GIVEN** a linkml-runtime or FastAPI release without the caches the release clears
- **WHEN** the tooling tests run
- **THEN** a test fails naming the library

## MODIFIED Requirements

### Requirement: The unit and feature tests run in parallel

`make test` SHALL run the unit and feature tests on several worker processes (`pytest-xdist`) with
the same coverage floor as before. The worker count SHALL be the machine's core count minus 3 on a
machine of more than 6 cores, and the core count otherwise, and no more than the available memory
divided by `PYTEST_WORKER_MB` (default 1536), at least 1, counted when the run leaves the queue;
`PYTEST_N` SHALL override it.

#### Scenario: make test
- **WHEN** `make test` runs
- **THEN** pytest reports several workers, every test passes and coverage is measured over all of them

#### Scenario: the worker count
- **GIVEN** a machine with 20 cores, 40 GB available and no `PYTEST_N`
- **WHEN** `make test-fast` runs
- **THEN** pytest starts 17 workers

#### Scenario: little memory available
- **GIVEN** a machine with 20 cores, 12 GB available and no `PYTEST_N`
- **WHEN** `make test-fast` leaves the queue
- **THEN** pytest starts 8 workers, and the run says so

### Requirement: The tests of the changed files run on their own

`make test-changed` SHALL run, without coverage, the unit and feature tests that the files changed
against the merge base with `develop` (committed, uncommitted and untracked) reach, slow tests
included. When the worktree has selection data (`make test-seed`), a changed Python file under
`rdf_persistence/`, `rdf_persistence_generation/` or `tests/` (container and perf tests and
`tests/fixtures/` aside)
SHALL select the tests whose execution recorded by the seed it touches; the selection SHALL NOT
change the recorded data, so the same changes select the same tests on every run. A file under
`rdf_persistence_generation/` or `tests/generator/` SHALL also select `tests/generator/`. Every
other file SHALL select by folder: a file of `rdf_persistence/<theme>/` selects
`tests/unit/<theme>/`, a test under a folder of `tests/unit/` selects that folder, a file under
`docs/` selects the docs check. Without selection data every file SHALL select
by folder, and the command SHALL say that the lead runs `make test-seed`. A change in the `core`
theme, to shared test infrastructure, or to a file that neither rule maps SHALL run `make test-fast`
instead, except that with selection data a Python file selected by recorded execution never
does; the selection data SHALL count as absent when the installed packages differ from those the
seed recorded. Selected folders and the
selection by recorded execution SHALL run in parallel; a selection of test files alone SHALL run on
one process. Parallel runs of
`make test-changed` SHALL use at most `PYTEST_CHANGED_N` workers (default 4). Container tests SHALL
NOT run; a changed container test SHALL be named with the hint `make test-containers`.

#### Scenario: a change in one layer
- **GIVEN** a branch whose only change against `develop` is in `rdf_persistence/persistence/services/`
  and a worktree without selection data
- **WHEN** `make test-changed` runs
- **THEN** pytest runs `tests/unit/persistence/`, its slow tests included, and no other folder, and
  the output names `make test-seed`

#### Scenario: a change in the core theme, with selection data
- **GIVEN** selection data and a branch whose only change is one function of
  `rdf_persistence/core/domain/sparql.py`
- **WHEN** `make test-changed` runs
- **THEN** pytest runs the tests that executed that function, `tests/unit/core/test_sparql.py`
  among them, and not `make test-fast`

#### Scenario: a change in the core theme
- **GIVEN** no selection data and a branch whose only change is in `rdf_persistence/core/domain/`
- **WHEN** `make test-changed` runs
- **THEN** it runs `make test-fast` and says that `core` is imported by every theme

#### Scenario: a changed test helper, with selection data
- **GIVEN** selection data and an edited `tests/library_app.py` and `tests/e2e/world.py`
- **WHEN** `make test-changed` runs twice
- **THEN** each run executes the same tests, those that executed the helpers, and not
  `make test-fast`

#### Scenario: a change outside a theme
- **GIVEN** no selection data and a branch whose only change against `develop` is
  `rdf_persistence/__init__.py`
- **WHEN** `make test-changed` runs
- **THEN** pytest runs `tests/unit/package/` and no theme folder

#### Scenario: a changed test file
- **GIVEN** no selection data and an edited `tests/unit/tenancy/test_tenancy_stores.py` and nothing else
- **WHEN** `make test-changed` runs
- **THEN** pytest runs `tests/unit/tenancy/`, in parallel

#### Scenario: a changed root-level test file
- **GIVEN** no selection data and an edited test file directly in `tests/unit/` (a new one) and
  nothing else
- **WHEN** `make test-changed` runs
- **THEN** pytest runs that file only, on one process

#### Scenario: a changed tooling test file
- **GIVEN** no selection data and an edited `tests/unit/tooling/test_markers.py` and nothing else
- **WHEN** `make test-changed` runs
- **THEN** pytest runs `tests/unit/tooling/`, in parallel

#### Scenario: a change to shared test infrastructure
- **GIVEN** no selection data and an edited `tests/conftest.py`, `pytest.ini`, `pyproject.toml`,
  `uv.lock`, `Makefile`, `tests/toy_service.py`, a schema under `rdf_persistence/model/` or
  `tests/e2e/library_app.py`
- **WHEN** `make test-changed` runs
- **THEN** it runs `make test-fast` and says why

#### Scenario: a change to shared configuration, with selection data
- **GIVEN** selection data and an edited `pytest.ini`, `Makefile`, `.coveragerc`,
  `pyproject.toml`, `uv.lock`, a schema under `rdf_persistence/model/` or a file under
  `tests/fixtures/`
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
