# rp-schema-migrations Specification

## Purpose
Keep stored data in step with the schema: each database records the schema version its data
follows, `rp-generate` decides from a committed lock which schema changes need a migration, and
reviewed migration files run at start-up and on a restored dump. Created by the change
`schema-migrations` (archived 2026-11-15).
## Requirements
### Requirement: Each database records the schema version its data follows

Every database (the system database, the application database and each tenant's) SHALL record, per
schema, the version of that schema its stored data follows, as one plain-string statement in the
database's schema-stamps graph. A service instance SHALL not read or write the aggregates of a
tenant whose migration failed at that instance's start-up; it SHALL still let the tenant's record
be read, its grants be changed, the tenant be deleted or dumped. A tenant, system or application
database created by a service SHALL record the versions that service runs.

#### Scenario: a new tenant
- **GIVEN** a library service whose schema is at version 2
- **WHEN** a tenant is created
- **THEN** its database records version 2 of the library schema and the toolkit's metamodel version

#### Scenario: a tenant behind the schema
- **GIVEN** a library tenant whose migration failed at start-up
- **WHEN** a reader gets one of its books
- **THEN** the service answers 503 with the problem `tenant-behind`, and serves other tenants

### Requirement: A schema change that stored data must follow needs a new version and a migration

`rp-generate` SHALL compare the schema with the committed lock of its previous state and SHALL
accept additive changes as they are, draft a migration that drops the data of a removed slot,
draft an unresolved step for every other change that stored data must follow, and refuse such a
change when the schema's version is unchanged. A root schema whose data is stored SHALL declare a
version and a migrations folder.

#### Scenario: an added optional slot
- **GIVEN** the library schema with its lock
- **WHEN** a book gains an optional slot and the developer regenerates
- **THEN** generation succeeds and no migration is asked for

#### Scenario: a removed slot without a new version
- **GIVEN** the library schema with its lock
- **WHEN** a slot is removed from the book, the version stays, and the developer regenerates
- **THEN** generation fails, naming the class and the slot, and asks for a new version

#### Scenario: a removed slot with a new version
- **GIVEN** the library schema with its lock
- **WHEN** a slot is removed from the book, the version is raised, and the developer regenerates
- **THEN** a migration file is drafted that drops the slot's values, and a file the developer edited is never overwritten

#### Scenario: a change that would change stored IRIs
- **GIVEN** the library schema with its lock
- **WHEN** the book class is renamed so that the IRIs of stored books would change, and the developer regenerates
- **THEN** generation fails, saying the change cannot be migrated

#### Scenario: an unresolved draft
- **GIVEN** a drafted migration with a step still marked unresolved
- **WHEN** the developer regenerates, or the service starts
- **THEN** it fails, naming the file and the step

### Requirement: Migrations run once, in order, and leave a tenant usable

At start-up the toolkit SHALL apply each pending migration to each database once, in the order of
the chain of versions, the toolkit's own before the consumer's, changing the data and the recorded
version in one atomic request per migration, and a migration that fails SHALL leave that
database's data and recorded version as they were before that migration (migrations of the chain
that succeeded before it stay applied). A failing tenant SHALL not stop the other tenants; a
failing system or application database SHALL stop the service from starting.

#### Scenario: a renamed slot
- **GIVEN** a stored book and a new schema version that renames one of its slots, with its migration
- **WHEN** the service starts
- **THEN** the book holds the value under the new slot, its shape validates, and the tenant records the new version

#### Scenario: a second start
- **GIVEN** a tenant already migrated
- **WHEN** the service starts again, or a second instance starts at the same time
- **THEN** the migration is applied once and nothing changes

#### Scenario: a failing migration
- **GIVEN** a migration that fails on one tenant
- **WHEN** the service starts
- **THEN** that tenant keeps its previous data and version, the failure names the tenant and the migration, and the other tenants are migrated

#### Scenario: what a migration leaves alone
- **GIVEN** a book with an owned part and a loaded graph
- **WHEN** a migration runs
- **THEN** the part is migrated with its book, the loaded graph and the registry are unchanged

#### Scenario: a client with an old version token
- **GIVEN** a client that read a book before a migration with steps
- **WHEN** it replaces the book with the version token it holds
- **THEN** the service answers with a conflict

### Requirement: A dump carries the version of its data and a restore migrates it

A dump's manifest SHALL record the schema version the tenant's data follows (its stamp; none when
the tenant has no stamp), and a restore SHALL accept a dump of the service's schema at any version
of its chain, migrate it to the running versions in memory before its graphs and root are checked and imported, and
refuse, creating nothing, a dump with no version, an unknown one, or one whose manifest version
differs from the stamp the dump holds.

#### Scenario: a dump whose manifest disagrees with its stamp
- **GIVEN** a dump whose manifest records version 2 while its stamps graph holds version 1
- **WHEN** it is restored
- **THEN** the service refuses it, naming both versions, and creates nothing

#### Scenario: restoring an older dump
- **GIVEN** a dump of a library tenant taken at version 1 and a service at version 2 with its migration
- **WHEN** the dump is restored
- **THEN** the new tenant's data follows version 2

#### Scenario: a dump from an unknown version
- **GIVEN** a dump whose version is not in the service's chain
- **WHEN** it is restored
- **THEN** the service refuses it and creates nothing

