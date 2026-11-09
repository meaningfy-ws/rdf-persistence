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

### Requirement: The unit and feature tests run in parallel

`make test` SHALL run the unit and feature tests on several worker processes (`pytest-xdist`,
`-n auto`) with the same coverage floor as before.

#### Scenario: make test
- **WHEN** `make test` runs
- **THEN** pytest reports several workers, every test passes and coverage is measured over all of them

### Requirement: CI runs the static checks and the tests in parallel jobs, without containers

The CI workflow SHALL run one job per make group, in parallel: `check-style`, `check-types`,
`check-architecture`, `check-spec-docs` with `check-generation`, `test-unit` and `test-feature`;
each group SHALL be a make target that runs alone. `test-unit` SHALL fail under 80 % coverage and
`test-feature` under 50 %.
CI SHALL NOT run container, e2e or Fuseki work; `make test-containers` runs locally.

#### Scenario: a failing lint in CI
- **GIVEN** a PR with a lint error and failing unit tests
- **WHEN** CI runs
- **THEN** the style and unit jobs both fail and report, without one waiting for the other

#### Scenario: no containers in CI
- **WHEN** CI runs on a PR or a push to develop
- **THEN** no job starts a Docker container or builds the Fuseki image

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

