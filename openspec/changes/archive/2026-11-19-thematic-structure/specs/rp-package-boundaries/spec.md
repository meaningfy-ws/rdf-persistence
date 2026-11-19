## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Themes import in one order

The themes SHALL import only themes below them, in the order `core`; `iris`, `schema`;
`provenance`, `files`; `persistence`; `access`, `migrations`; `tenancy`; `collaboration`, `events`;
`messaging`; `api`, where themes named together import neither the other.

#### Scenario: a theme imports one above it
- **WHEN** a module of `rdf_persistence/collaboration/` imports from `rdf_persistence/messaging/`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: two themes of one rank
- **WHEN** a module of `rdf_persistence/events/` imports from `rdf_persistence/collaboration/`
- **THEN** `make check-architecture` fails and names both modules

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
