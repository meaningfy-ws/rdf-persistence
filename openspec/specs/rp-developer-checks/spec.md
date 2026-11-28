# rp-developer-checks Specification

## Purpose
The checks a developer and CI run on this repository: they give the same answer on every run,
the unit and feature tests run in parallel, CI runs one parallel job per make group without
containers, and the testing checklist names only public testkit helpers.

## Requirements

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
- **GIVEN** a local `temp/fuseki-image.tar` newer than `fuseki/` and `compose.yaml`
- **WHEN** `make fuseki-image` and then `make test-containers` run
- **THEN** Fuseki starts from the loaded image, without fetching from `repo1.maven.org`

#### Scenario: an unformatted file
- **GIVEN** a Python file that `ruff format` would change
- **WHEN** `make check-all` runs
- **THEN** it fails naming the file

#### Scenario: a timing budget under load
- **GIVEN** a test that asserts a wall-clock budget
- **WHEN** `make check-all` runs on a loaded machine
- **THEN** the test does not run; `make test-perf` runs it

#### Scenario: the worker count read under load
- **GIVEN** the free memory changes while `make check-all` runs, so the worker count make computes
  changes from one expansion of `PYTEST_N` to the next
- **WHEN** `test_on_ci_pytest_runs_unqueued_with_the_workers_counted_by_make` runs
- **THEN** it reads the count once, from `PARALLEL`, and passes whenever that count is a whole
  number within the worker bounds

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

### Requirement: CI runs the static checks and the tests in parallel jobs, without containers

The CI workflow SHALL run on pull requests into `develop`, one job per make group, in parallel:
`check-style`, `check-types`, `check-architecture`, `check-spec-docs` with `check-generation`, and
`test-feature`; each group SHALL be a make target that runs alone. It SHALL NOT run the unit lane or
`test-generator`. A nightly workflow SHALL run on a schedule and by hand, on `develop`: the unit
lane in shards whose combined coverage SHALL fail under 80 % of `rdf_persistence`, and
`test-generator`, which SHALL fail under 80 % coverage of `rdf_persistence_generation`.
`test-feature` SHALL fail under 50 %; `test-unit` and `test-feature` SHALL NOT collect
`tests/generator/`. `test-generator` SHALL run the generator's unit, feature and integration tests.
Neither workflow SHALL run container, e2e or Fuseki work; `make test-containers` runs locally.

#### Scenario: a failing lint in CI
- **GIVEN** a PR with a lint error and a failing feature test
- **WHEN** CI runs
- **THEN** the style and feature jobs both fail and report, without one waiting for the other

#### Scenario: no containers in CI
- **WHEN** CI runs on a PR, or the nightly workflow runs
- **THEN** no job starts a Docker container or builds the Fuseki image

#### Scenario: a PR runs no unit or generator tests
- **GIVEN** a PR into `develop`
- **WHEN** CI runs
- **THEN** no job runs `make test-unit-ci` or `make test-generator`, and the PR's gate takes minutes,
  not a quarter of an hour

#### Scenario: a generator change
- **GIVEN** a commit on `develop` that breaks a generator test only
- **WHEN** the nightly workflow runs
- **THEN** its `test-generator` job fails and its unit jobs pass

### Requirement: The testing checklist names only public helpers

`make check-docs` SHALL fail when `develop/testing.adoc` names a `testkit.<name>` that
`rdf_persistence.testkit` does not list in `__all__`.

#### Scenario: a helper the testkit does not export
- **GIVEN** `develop/testing.adoc` names `testkit.some_helper`
- **WHEN** `make check-docs` runs
- **THEN** it fails naming `some_helper`

### Requirement: Agents' shell commands do not poll

The repository's Claude Code settings SHALL run a `PreToolUse` hook on every Bash call that denies
a command looping with `sleep` (an `until`, `while` or `for` loop whose body runs `sleep`), with a
reason that names the alternatives: the foreground with a timeout of up to 10 minutes (600000 ms),
a background run and its completion notice, or the Monitor tool. The hook SHALL allow every other
command, except that a command which only quotes such a loop, or in which a `sleep` and a later
`done` follow a loop without `sleep`, MAY be denied. The hook SHALL let the command run when the
hook itself fails.

#### Scenario: an agent polls a background check
- **GIVEN** an agent session in this repository
- **WHEN** it runs `until grep -q real temp/checkall.log; do sleep 5; done; tail temp/checkall.log`
- **THEN** the command does not run, and the agent receives the reason naming the foreground and the
  completion notice

#### Scenario: a single pause before a command
- **GIVEN** an agent session in this repository
- **WHEN** it runs `sleep 5; gh pr merge 41 --merge`
- **THEN** the command runs

#### Scenario: a loop without sleep
- **GIVEN** an agent session in this repository
- **WHEN** it runs `for s in wait_until fuseki; do gitnexus impact $s; done`
- **THEN** the command runs

#### Scenario: the hook cannot read its input
- **GIVEN** the hook receives input that is not a Bash tool call
- **WHEN** it runs
- **THEN** it exits without denying, and the command runs

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

### Requirement: The fast lane leaves out slow tests

`make test-fast` SHALL run every unit and feature test not marked `slow`, in parallel, without
coverage. A test that takes seconds on its own, because it runs a tool, a subprocess or a whole
generation, SHALL carry `@pytest.mark.slow`. `make check-all`, `make test`, `make test-unit` and
`make test-feature` SHALL run slow tests too, with their coverage floors unchanged; the nightly
unit shards SHALL leave them out.

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

### Requirement: The docs' diagrams render with the site's mermaid

The `Makefile` SHALL pin one mermaid version (`MERMAID_VERSION`). `make check-docs` SHALL fail when
an Antora playbook loads another mermaid version. `make check-diagrams` SHALL render every
`[mermaid]` block of every docs page with that version, and SHALL fail when one does not render.
CI SHALL run both.

#### Scenario: a playbook loads another mermaid
- **GIVEN** the `Makefile` pins mermaid 12.3.0 and a playbook loads `mermaid@10`
- **WHEN** `make check-docs` runs
- **THEN** it fails naming the playbook

#### Scenario: a diagram does not parse
- **GIVEN** a docs page with a sequence diagram whose message holds a `;`
- **WHEN** `make check-diagrams` runs
- **THEN** it fails with the parse error, and the page is not published broken

### Requirement: A test cannot hang the checks

Every pytest run, parallel (xdist) or serial, SHALL stop a test that runs longer than 120 s, fail
it naming it, and run the next test (the worker survives), and every CI job SHALL stop after 30
minutes, except the unit-test job, which SHALL stop after 60 minutes (it takes about 30 minutes on
a hosted runner).

#### Scenario: a test that never returns, in a parallel lane
- **GIVEN** a unit test that awaits an event nobody sets
- **WHEN** `make test` runs (parallel, `-n auto`)
- **THEN** the test fails after 120 s naming itself, the worker is not replaced, and the other tests still run

#### Scenario: a test that never returns, in a serial run
- **GIVEN** a unit test that awaits an event nobody sets
- **WHEN** pytest runs it without xdist
- **THEN** the test fails after 120 s naming itself, and the next test still runs

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

### Requirement: The coverage floor covers the adapters

The unit and feature coverage floors SHALL measure every module of `rdf_persistence` except the
generated code and the modules that need a running container (`adapters/redis_events.py` and
`testkit/containers/`), which `make test-containers` exercises.

#### Scenario: an untested adapter
- **GIVEN** a new adapter module that no unit test imports
- **WHEN** `make test-unit` runs
- **THEN** the module counts at 0 % towards the 80 % floor

### Requirement: The lint selection is the Meaningfy template's

`make lint` SHALL run Ruff with the project-setup template's selection, including `S113`, `DTZ`,
`BLE001`, `TID251`, `PLR2004`, `PLR0912`, `PLR0913`, `PLR0915` and `PT018`; every suppression
SHALL name its code and its reason.

#### Scenario: a composite assertion
- **GIVEN** a test with `assert a and b`
- **WHEN** `make lint` runs
- **THEN** it fails with `PT018` naming the file and line

### Requirement: Every docs link resolves to a page and an anchor

`make check-docs` SHALL fail when an `xref:` in a docs page or in the nav names a page that does
not exist in the component (an alias declared with `:page-aliases:` counts as a page) or an anchor
the target page does not define, and when a `<<anchor>>` names an anchor its own page does not
define. An anchor is defined by `[#id]`, `[[id]]`, `anchor:id[]` or by a section title, whose
implicit id SHALL be computed as Asciidoctor computes it with the `idprefix` and `idseparator` the
site playbook sets (today `''` and `-`).

#### Scenario: a link to a moved section
- **GIVEN** a page links to `xref:user-manual/tenants.adoc#tenancy[...]` and no page defines that id there
- **WHEN** `make check-docs` runs
- **THEN** it fails naming the page, the link and the missing anchor

#### Scenario: a link through an alias
- **GIVEN** a page links to `xref:howto/adopt.adoc[...]` and `user-manual/index.adoc` declares `:page-aliases: howto/adopt.adoc`
- **WHEN** `make check-docs` runs
- **THEN** the link passes

### Requirement: The generated reference is fresh

`make check-docs` SHALL fail when the reference partials written by `docs/tools/reference.py`
(the public Python API from `rdf_persistence.__all__` and the `rp-generate` usage) differ from what
the tool would write now.

#### Scenario: a name added to the public API
- **GIVEN** a name is added to `rdf_persistence.__all__` and the partials are not rewritten
- **WHEN** `make check-docs` runs
- **THEN** it fails saying the reference is stale and naming the command that rewrites it

### Requirement: Heavy test runs queue on the machine

Every make target that runs a parallel test lane, `make test-containers` and `make test-seed` SHALL
run its pytest command behind one lock shared by every repository the same user runs on the
machine, so that one such run of that user executes at a time. A run that waits SHALL say once
whose run holds the lock (folder, command, process, start time), and, when it starts, how long it
waited. The lock SHALL be released when the run ends, however it ends.
A named-file run (`uv run pytest <file>`) and `make test-changed`'s own runs SHALL NOT take the lock.

#### Scenario: two sessions start a lane
- **GIVEN** a session running `make test-fast` in one repository
- **WHEN** another session of the same user starts `make check-all` in another repository on the
  same machine
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

### Requirement: The whole seed cycle runs inside one queued run

`make test-seed` SHALL delete the seed files of an earlier run, run the tests and swap the new
data in, all inside one run that holds the test queue, so that a second seed starts only after the
first has swapped. When the deletion fails, the seed SHALL stop with a non-zero exit and run no
test.

#### Scenario: two seeds in one worktree
- **GIVEN** `make test-seed` running in a worktree
- **WHEN** a second `make test-seed` starts in the same worktree
- **THEN** the second waits for the queue, and the first run's seed database is swapped in intact

### Requirement: The changed-files run neither syncs nor hides its hints

`make test-changed` SHALL NOT synchronise the project environment. When it falls back to the fast
lane, it SHALL print its hints (such as `make test-seed` when no selection data exists) before
the fallback reasons.

#### Scenario: a package file changed without selection data
- **GIVEN** a worktree without selection data
- **WHEN** a theme file and one shared file change and `make test-changed` runs
- **THEN** stderr names `make test-seed` and the fallback reason, and the fast lane runs

#### Scenario: the lock file changed
- **WHEN** `uv.lock` changed and `make test-changed` runs
- **THEN** the environment is not synchronised, and the fast lane runs

### Requirement: A bad worker count is a usage error

A `PYTEST_CHANGED_N` that is not an integer of at least 1 SHALL end `make test-changed` with exit
status 2 and one line naming the value, before any test runs.

#### Scenario: a bad count
- **WHEN** `PYTEST_CHANGED_N` is `abc`, `0`, `-1` or `2.5` and `make test-changed` runs
- **THEN** it prints `PYTEST_CHANGED_N must be a positive integer, got '<value>'` and exits 2

### Requirement: CI counts workers quietly and never passes the token

Under `CI`, the worker count SHALL be computed only when a recipe needs it, print nothing on
failure, and fall back to pytest's own `auto` when it cannot be computed.

#### Scenario: a job without uv
- **GIVEN** `CI` set and no `uv` on the path
- **WHEN** a target that runs no test (`make lint`) is parsed
- **THEN** nothing is printed about `uv`

#### Scenario: no count
- **GIVEN** `CI` set and an empty `PYTEST_N`
- **WHEN** a parallel lane runs
- **THEN** pytest receives `-n auto`
