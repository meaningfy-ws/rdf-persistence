## MODIFIED Requirements

### Requirement: Layers import downward only

The layers SHALL import as `entrypoints | adapters > services > domain`: entrypoints and adapters
from services and domain, services from domain, domain from nothing in the package; `generation`
and `testkit` MAY import any layer. A generated technical model SHALL sit in the `generated/`
package of the lowest layer every user of it may import, so the layers order it like any other
module of that layer, and no module of the domain layer SHALL import a technical model.

#### Scenario: a service imports an adapter
- **WHEN** a module in `rdf_persistence/services/` imports from `rdf_persistence/adapters/`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: a service imports a wire model
- **WHEN** a module in `rdf_persistence/services/` imports from `rdf_persistence.adapters.generated`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: a domain module imports a technical model
- **WHEN** a module in `rdf_persistence/domain/` imports from `rdf_persistence.services.generated`
- **THEN** `make check-architecture` fails and names both modules
