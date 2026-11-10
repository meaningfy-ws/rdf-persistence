## ADDED Requirements

### Requirement: A tenant's database may live on another store

The service kit SHALL accept several named stores, SHALL record in each access record the store of
the tenant's database, and SHALL read and write each tenant only on its own store.

#### Scenario: two tenants on two stores
- **GIVEN** a kit wired to two stores and one tenant created on each
- **WHEN** a book is written to each tenant
- **THEN** each book is stored only on its tenant's store and reads back from it
