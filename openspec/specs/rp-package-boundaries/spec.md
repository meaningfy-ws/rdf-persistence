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

The package SHALL be divided into themes (`rdf_persistence/<theme>/`), each holding only the layers
it needs. Inside a theme and across themes, the layers SHALL import as
`entrypoints | adapters > services > domain`: entrypoints and adapters from services and domain,
services from domain, domain from no other layer of any theme; `testkit` MAY import any layer. The
generator is a sibling package outside the layers and MAY import any of them. A generated
technical model SHALL sit in the `generated/` package of the lowest layer every user of it may
import, in the lowest theme that uses it, so the layers order it like any other module of that
layer, and no module of a domain layer SHALL import a technical model. No module of a theme SHALL
sit outside its layers.

#### Scenario: a service imports an adapter
- **WHEN** a module in `rdf_persistence/persistence/services/` imports from `rdf_persistence/access/adapters/`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: a service imports a wire model
- **WHEN** a module in `rdf_persistence/tenancy/services/` imports from `rdf_persistence.access.adapters.generated`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: a domain module imports a technical model
- **WHEN** a module of `rdf_persistence/iris/domain/` imports `ServiceSettings` from `rdf_persistence.iris.services.generated`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: a domain module imports a service of another theme
- **WHEN** a module in `rdf_persistence/iris/domain/` imports from `rdf_persistence/core/services/`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: a module outside the layers
- **WHEN** a module `rdf_persistence/tenancy/helpers.py` is added
- **THEN** `make check-architecture` fails and names it

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

### Requirement: Themes import in one order

The themes SHALL import only themes below them, in the order `core`; `iris`, `schema`;
`provenance`; `files`; `persistence`; `access`, `migrations`; `tenancy`; `collaboration`, `events`;
`messaging`; `api`, where themes named together import neither the other.

#### Scenario: a theme imports one above it
- **WHEN** a module of `rdf_persistence/collaboration/` imports from `rdf_persistence/messaging/`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: two themes of one rank
- **WHEN** a module of `rdf_persistence/events/` imports from `rdf_persistence/collaboration/`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: files above provenance
- **WHEN** a module of `rdf_persistence/files/domain/` imports from `rdf_persistence/provenance/domain/`
- **THEN** `make check-architecture` passes, and the reverse import fails naming both modules

### Requirement: The public names survive the move, the old deep paths do not

Every name exported from `rdf_persistence` SHALL stay the same object through the move, except
`mint_aggregate_iri`, which SHALL be removed. The old deep paths `rdf_persistence.domain.base` and
`rdf_persistence.adapters.fuseki` SHALL be removed in the release that moves the themes, with no
deprecation period (D-26); a consumer's generated code SHALL import `RpModel` from
`rdf_persistence`, and its freshness check SHALL ask it to regenerate once.

#### Scenario: a consumer's generated code before it regenerates
- **GIVEN** a consumer module with `from rdf_persistence.domain.base import RpModel`
- **WHEN** it is imported in the release that moves the themes
- **THEN** it fails with `ModuleNotFoundError`, and the consumer's freshness check names its generated code as stale

#### Scenario: the public names
- **WHEN** a consumer imports `FusekiStore`, `Tenancy` and `ServiceKit` from `rdf_persistence`
- **THEN** it gets the same classes as before the move, with no warning
