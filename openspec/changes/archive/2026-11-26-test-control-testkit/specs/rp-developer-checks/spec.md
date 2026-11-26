<!-- Capability: rp-developer-checks. EPIC test-control-testkit, DEC-2, DEC-3; design PD-5 to PD-10. -->

## MODIFIED Requirements

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

## ADDED Requirements

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
