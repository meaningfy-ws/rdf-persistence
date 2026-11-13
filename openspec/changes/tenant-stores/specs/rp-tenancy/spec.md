## ADDED Requirements

### Requirement: A tenant's database may live on another wired store

The service kit SHALL accept named stores beside its `default` store, SHALL create a tenant's
database on the store the creator names (`default` when none is named), SHALL record that store's
name in the access record, and SHALL read, write, sweep and delete each tenant only on its own store.
A record without a store name SHALL mean `default`. The system database SHALL stay on `default`.

#### Scenario: two tenants on two stores
- **GIVEN** a kit wired to `default` and `client-a`, and one tenant created on each
- **WHEN** a book is written to each tenant
- **THEN** each book is stored only on its tenant's store and reads back from it

#### Scenario: an existing record
- **GIVEN** an access record written before store names existed
- **WHEN** its tenant is read
- **THEN** the session opens on the `default` store

#### Scenario: deletion on the tenant's store
- **GIVEN** a tenant on `client-a`
- **WHEN** it is deleted
- **THEN** its database is dropped from `client-a` and nothing is dropped on `default`

### Requirement: The start-up sweep covers every wired store

The start-up sweep SHALL drop a tenant-prefixed database on any wired store only when no access
record names that database, and SHALL finish interrupted deletions on the tenant's own store. The
service SHALL refuse to start, naming the store, when an access record names a store that is not
wired.

#### Scenario: an orphan on another store
- **GIVEN** a tenant-prefixed database on `client-a` that no access record names, and an active tenant on `client-a`
- **WHEN** the service starts
- **THEN** the orphan is dropped and the active tenant's database is unchanged

#### Scenario: a store that is no longer wired
- **GIVEN** an access record naming store `client-b`, and a kit wired to `default` and `client-a`
- **WHEN** the service starts
- **THEN** it refuses to start, naming `client-b`, and drops nothing
