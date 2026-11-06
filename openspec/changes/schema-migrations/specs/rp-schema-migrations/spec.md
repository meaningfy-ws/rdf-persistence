## ADDED Requirements

### Requirement: Each tenant records the schema version its data follows

Every tenant SHALL record the version of the consumer's schema its stored data follows, and the
service SHALL not serve a tenant's aggregates while that version is behind the schema it runs.

#### Scenario: a tenant behind the schema
- **GIVEN** a library tenant whose recorded version is older than the running schema and no migration has run
- **WHEN** a reader gets one of its books
- **THEN** the service refuses with a problem response saying the tenant is being migrated, and serves other tenants

### Requirement: Migrations run once, in order, and leave a tenant usable

The toolkit SHALL apply each pending migration to a tenant once, in version order, recording the new
version only after the migration succeeds, and a migration that fails SHALL leave the tenant's data
and recorded version as they were before it.

#### Scenario: a renamed slot
- **GIVEN** a stored book and a new schema version that renames one of its slots, with its migration
- **WHEN** migrations run
- **THEN** the book holds the value under the new slot, its shape validates, and the tenant records the new version

#### Scenario: a failing migration
- **GIVEN** a migration that fails on one tenant
- **WHEN** migrations run
- **THEN** that tenant keeps its previous data and version, and the failure names the tenant and the migration
