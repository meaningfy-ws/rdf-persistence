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

The themes SHALL import only themes below them, in the order `core`; `iris`, `schema`, `files`;
`provenance`; `persistence`; `access`, `migrations`; `tenancy`; `collaboration`, `events`;
`messaging`; `api`, where themes named together import neither the other.

#### Scenario: a theme imports one above it
- **WHEN** a module of `rdf_persistence/collaboration/` imports from `rdf_persistence/messaging/`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: two themes of one rank
- **WHEN** a module of `rdf_persistence/events/` imports from `rdf_persistence/collaboration/`
- **THEN** `make check-architecture` fails and names both modules

### Requirement: A moved public path warns for one release

A deep path a consumer may have imported SHALL keep working after the move, warning, for one
release: `rdf_persistence.domain.base` and `rdf_persistence.adapters.fuseki` SHALL keep working for one minor release after the move, each
raising a `DeprecationWarning` that names its new path, and SHALL be removed in the next minor
release. Every name exported from `rdf_persistence` SHALL stay the same object through the move,
except `mint_aggregate_iri`, which SHALL warn for the same release and then be removed.

#### Scenario: a consumer's generated code before it regenerates
- **GIVEN** a consumer module with `from rdf_persistence.domain.base import RpModel`
- **WHEN** it is imported in the release that moves the themes
- **THEN** it works, a `DeprecationWarning` names `rdf_persistence.core.domain.base`, and `RpModel` is `rdf_persistence.RpModel`

#### Scenario: the public names
- **WHEN** a consumer imports `FusekiStore`, `Tenancy` and `ServiceKit` from `rdf_persistence`
- **THEN** it gets the same classes as before the move, with no warning
