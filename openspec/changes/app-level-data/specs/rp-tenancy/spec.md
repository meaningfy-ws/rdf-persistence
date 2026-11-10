## ADDED Requirements

### Requirement: The application keeps its own aggregates outside any tenant

The service kit SHALL let the application store, read, replace and delete its own aggregates
outside every tenant, versioned and access-checked like tenant aggregates, and SHALL never let such
a write change an access record.

#### Scenario: an application aggregate is not in any tenant
- **GIVEN** an application aggregate and a tenant
- **WHEN** the tenant's aggregates are listed and the application's aggregate is read
- **THEN** the listing does not include it and the read returns it
