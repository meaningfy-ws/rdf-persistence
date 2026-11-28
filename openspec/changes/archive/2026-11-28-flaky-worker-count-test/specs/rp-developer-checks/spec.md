## MODIFIED Requirements

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
