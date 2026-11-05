Capability: rp-package-boundaries. Source: EPIC `toolkit-v1-foundation` (DEC-6); design PD-1;
architecture `index.adoc` (public API and layer map). Moved here from the first consumer's
architecture change, where it was drafted, by decision D-12.

## ADDED Requirements

### Requirement: The toolkit depends on no consumer

The `rdf_persistence` package SHALL NOT import any consumer package, and its code, tests and
architecture pages SHALL NOT use consumer terms; the background study is exempt.

#### Scenario: a consumer term in an architecture page
- **WHEN** a page under `docs/modules/ROOT/pages/architecture/` contains "Mapping Workbench"
- **THEN** `make check-docs` fails and names the page

#### Scenario: tested alone
- **WHEN** CI runs this repository's tests with no consumer installed
- **THEN** all of them pass

### Requirement: Layers import downward only

The layers SHALL import as `entrypoints | adapters > services > domain`: entrypoints and adapters
from services and domain, services from domain, domain from nothing in the package; `generation`
and `testkit` MAY import any layer.

#### Scenario: a service imports an adapter
- **WHEN** a module in `rdf_persistence/services/` imports from `rdf_persistence/adapters/`
- **THEN** `make check-architecture` fails and names both modules

### Requirement: Consumers use the public API only

Every name a consumer needs SHALL be exported from the top-level `rdf_persistence` package (and
`rdf_persistence.testkit` for tests); the public API page SHALL list them.

#### Scenario: a name used by the toy library
- **WHEN** the toy library's end-to-end test imports anything from `rdf_persistence`
- **THEN** it imports only top-level names or `rdf_persistence.testkit`
