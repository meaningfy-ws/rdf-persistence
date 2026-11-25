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

### Requirement: Slots that share an IRI are locked apart

The lock SHALL keep each slot of a class, also when two slots share an IRI, and the comparison
SHALL pair them: a slot added on an IRI already locked SHALL be a slot added, never a change of
the other slot's range.

#### Scenario: a business identifier beside the identifier
- **GIVEN** a class locked with its identifier on `dcterms:identifier`
- **WHEN** the class gains an optional business slot on `dcterms:identifier`
- **THEN** the comparison reports one slot added, and generation succeeds without a new version

### Requirement: A migration renames or drops a role in the stored grants

A migration file MAY carry `grant_roles` with `rename` (old name to new name) and `drop` (names).
On the system database, the migration's request SHALL rename the role of every grant naming an
old name, deleting a grant whose renamed form the same assignee already holds on the same target,
and SHALL delete every grant naming a dropped name. It SHALL do this in the same stamp-guarded
request as the migration's steps, rotating the version tokens. Other databases SHALL get no grant
changes. Renames SHALL apply in file order, each completing before the next, and the drops
after them, so that two names renamed to one leave no duplicate grant. A rename SHALL apply to
grants at every level. A file that drops a name it also renames from or to, renames a name to
a renamed name or to itself, renames one name twice, renames a name to one that holds a comma,
or holds an empty name SHALL be refused when it is loaded, naming the file.

#### Scenario: two roles merged into one
- **GIVEN** an assignee holding both `reader` and `viewer` on the same target
- **WHEN** a migration renames `reader` to `member` and `viewer` to `member`
- **THEN** one `member` grant remains for them on that target, and the access record decodes

#### Scenario: a role renamed
- **GIVEN** a tenant whose grants name `reader`, and a pending migration with `rename: {reader: member}`
- **WHEN** start-up migrates the system database
- **THEN** those grants name `member`, the access record decodes, and its version changed

#### Scenario: a rename that meets an existing grant
- **GIVEN** an assignee holding both `reader` and `member` on the same target
- **WHEN** the migration renames `reader` to `member`
- **THEN** one `member` grant remains for them on that target

#### Scenario: a role dropped
- **GIVEN** a tenant whose grants name `guest`, and a migration with `drop: [guest]`
- **WHEN** start-up migrates
- **THEN** no grant names `guest`, and the other grants are unchanged

#### Scenario: a second run
- **WHEN** the same migration is sent again after the stamp moved
- **THEN** nothing changes

#### Scenario: a contradictory file
- **WHEN** a migration file names `guest` in both `rename` and `drop`
- **THEN** loading it is refused, naming the file
