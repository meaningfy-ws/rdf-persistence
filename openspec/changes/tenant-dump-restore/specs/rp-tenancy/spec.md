## ADDED Requirements

### Requirement: A tenant can be dumped and restored into a new tenant

The service kit SHALL export a tenant's named graphs as N-Quads together with its blobs, and SHALL
restore such a dump into a new tenant whose aggregates, loaded graphs and blobs read back as the
original's did.

#### Scenario: a restored tenant answers like the original
- **GIVEN** a library tenant with books, a loaded graph and a scan
- **WHEN** it is dumped and the dump is restored into a new tenant
- **THEN** every book, the loaded graph and the scan's bytes read back from the new tenant as from the original
