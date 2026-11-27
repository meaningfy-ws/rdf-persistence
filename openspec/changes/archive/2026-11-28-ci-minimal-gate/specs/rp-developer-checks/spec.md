## MODIFIED Requirements

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
