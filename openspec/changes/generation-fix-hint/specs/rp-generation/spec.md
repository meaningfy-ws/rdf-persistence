<!-- Capability: rp-generation. Change: generation-fix-hint (GitHub issue #25). -->

## MODIFIED Requirements

### Requirement: Stale or edited generated output is detected

`rp-generate --check` SHALL fail, naming the files, when an input of the last generation (the
schema closure, a template or an extension) has changed since, or when a generated file differs
from what was generated. The check SHALL run in `make check-quality`, at the start of every test
session and in CI. Its message SHALL end with a hint naming the command that regenerates: the
`regenerate-command` of each stale `[tool.rp-generate]` entry, or `rp-generate` for an entry that
sets none.

#### Scenario: a schema changed without regenerating
- **WHEN** a slot is added to the toy schema and `rp-generate` is not run
- **THEN** the test session stops before any test runs, naming the schema and the regenerating command

#### Scenario: a generated file edited by hand
- **WHEN** a line of a generated class file is changed by hand
- **THEN** `make check-quality` fails and names that file

#### Scenario: a model change is acknowledged
- **WHEN** a slot is added to the toy schema and the code is regenerated
- **THEN** the model-shape snapshot test fails until `make refresh-snapshot` is run

#### Scenario: an application that sets no command
- **GIVEN** a `[tool.rp-generate]` entry without `regenerate-command`
- **WHEN** its generated code is stale and the check runs through the CLI or the pytest plugin
- **THEN** the hint reads "run `rp-generate` to regenerate, then commit the result"

#### Scenario: an application that names its own command
- **GIVEN** a `[tool.rp-generate]` entry with `regenerate-command = "make generate-models"`
- **WHEN** its generated code is stale and the check runs through the CLI or the pytest plugin
- **THEN** the hint reads "run `make generate-models` to regenerate, then commit the result"

#### Scenario: a configuration error
- **GIVEN** a `[tool.rp-generate]` entry with an unknown key
- **WHEN** the pytest plugin runs
- **THEN** the session stops naming the key, and no regenerating command is suggested
