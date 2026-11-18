## MODIFIED Requirements

### Requirement: CI runs the static checks and the tests in parallel jobs, without containers

The CI workflow SHALL run one job per make group, in parallel: `check-style`, `check-types`,
`check-architecture`, `check-spec-docs` with `check-generation`, `test-unit`, `test-feature` and
`test-generator`; each group SHALL be a make target that runs alone. `test-unit` SHALL fail under
80 % coverage of `rdf_persistence` and `test-feature` under 50 %; `test-unit` and `test-feature`
SHALL NOT collect `tests/generator/`. `test-generator` SHALL run the generator's unit, feature and
integration tests and fail under 80 % coverage of `rdf_persistence_generation`.
CI SHALL NOT run container, e2e or Fuseki work; `make test-containers` runs locally.

#### Scenario: a failing lint in CI
- **GIVEN** a PR with a lint error and failing unit tests
- **WHEN** CI runs
- **THEN** the style and unit jobs both fail and report, without one waiting for the other

#### Scenario: no containers in CI
- **WHEN** CI runs on a PR or a push to develop
- **THEN** no job starts a Docker container or builds the Fuseki image

#### Scenario: a generator change
- **GIVEN** a PR that breaks a generator test only
- **WHEN** CI runs
- **THEN** the `test-generator` job fails and the `test-unit` job passes
