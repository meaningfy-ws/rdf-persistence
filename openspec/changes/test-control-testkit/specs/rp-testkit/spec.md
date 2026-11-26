<!-- Capability: rp-testkit. EPIC test-control-testkit, DEC-4 to DEC-8; design PD-1 to PD-4, PD-12 to PD-14. -->

## ADDED Requirements

### Requirement: A project queues and selects its tests with the testkit

The testkit SHALL ship the test queue (`rdf_persistence.testkit.run_queue`), the selection data
(`rdf_persistence.testkit.selection_data`) and the changed-tests planner
(`rdf_persistence.testkit.changed_tests`) as public modules run with `python -m` from the
installed package. A project SHALL supply only a classifier (what a changed path selects, and
which paths testmon sees) and a layout; the planning, the pytest runs, the exit codes and the
locks SHALL be the testkit's. The modules SHALL NOT be loaded by importing the testkit's root, and
SHALL directly import nothing of the library but the testkit's generated types (and, for the
planner, the selection data).

#### Scenario: run from outside the repository
- **GIVEN** an environment with the toolkit installed and a working directory outside its repository
- **WHEN** `python -I -m rdf_persistence.testkit.run_queue --workers` runs
- **THEN** it prints a positive worker count and exits 0

#### Scenario: a project's own classifier
- **GIVEN** a classifier that maps `src/app/x.py` to `tests/unit/app/`
- **WHEN** the planner runs with `src/app/x.py` changed and no selection data
- **THEN** it runs pytest on `tests/unit/app/` with the layout's ignores and markers, and hints
  that the lead runs `make test-seed`

#### Scenario: the root stays light
- **WHEN** a test imports `rdf_persistence.testkit`
- **THEN** none of the three modules is loaded
