# rp-package-boundaries Specification

## Purpose
The shape of the package: no dependency on a consumer, layers that import downward only, a public API for consumers, and declared types.

## Requirements

### Requirement: The toolkit depends on no consumer

The `rdf_persistence` package SHALL NOT import any consumer package, and its code, tests and
architecture pages SHALL NOT use consumer terms; the background study is exempt.

#### Scenario: a consumer term in code
- **WHEN** a module under `rdf_persistence/` contains "Mapping Workbench"
- **THEN** `make check-quality` fails and names the file

#### Scenario: a consumer term in an architecture page
- **WHEN** a page under `docs/modules/ROOT/pages/architecture/` contains "Mapping Workbench"
- **THEN** `make check-docs` fails and names the page

#### Scenario: tested alone
- **WHEN** CI runs this repository's tests with no consumer installed
- **THEN** all of them pass

### Requirement: Layers import downward only

The layers SHALL import as `entrypoints | adapters > services > domain`: entrypoints and adapters
from services and domain, services from domain, domain from nothing in the package; `testkit` MAY
import any layer. The generator is a sibling package outside the layers and MAY import any of them.
A generated technical model SHALL sit in the `generated/` package of the lowest layer every user
of it may import, so the layers order it like any other module of that layer, and no module of
the domain layer SHALL import a technical model.

#### Scenario: a service imports an adapter
- **WHEN** a module in `rdf_persistence/services/` imports from `rdf_persistence/adapters/`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: a service imports a wire model
- **WHEN** a module in `rdf_persistence/services/` imports from `rdf_persistence.adapters.generated`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: a domain module imports a technical model
- **WHEN** a module in `rdf_persistence/domain/` imports from `rdf_persistence.services.generated`
- **THEN** `make check-architecture` fails and names both modules

### Requirement: Consumers use the public API only

Every name a consumer needs SHALL be exported from the top-level `rdf_persistence` package (and
`rdf_persistence.testkit` for tests, `rdf_persistence_generation.testkit` for the tests of
generated code); the public API page SHALL list them.

#### Scenario: a name used by the toy library
- **WHEN** the toy library's end-to-end test imports anything from `rdf_persistence`
- **THEN** `testkit.assert_public_imports` finds only top-level names or `rdf_persistence.testkit`

### Requirement: The package declares its types

The built wheel SHALL contain `rdf_persistence/py.typed` and `rdf_persistence_generation/py.typed`
(PEP 561), so a consumer's type checker analyses the toolkit's and the generator's annotations
without configuration.

#### Scenario: a typed consumer
- **GIVEN** a project that depends on rdf-persistence and has no mypy override for it
- **WHEN** mypy checks a module that imports `rdf_persistence` and `rdf_persistence.testkit`
- **THEN** it reports no `import-untyped` error, and a wrong argument type to a toolkit function is
  reported

#### Scenario: one wheel, two packages
- **WHEN** the wheel is built
- **THEN** it contains both packages, each with its `py.typed`, and the generator's model and
  templates

### Requirement: The library never imports the generator

The `rdf_persistence` package, its testkit included, SHALL NOT import the
`rdf_persistence_generation` package; the generator MAY import the library. The only exceptions
SHALL be the deprecation shims of the moved testkit modules, each named in the import contract,
for one minor release.

#### Scenario: a library module imports the generator
- **WHEN** a module under `rdf_persistence/` imports from `rdf_persistence_generation`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: a library test imports the generator
- **WHEN** a test outside `tests/generator/` imports `rdf_persistence_generation` and is not one of
  the named tests that use the generator as a tool on the library's own schemas
- **THEN** the unit tests fail and name the file
