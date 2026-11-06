# rp-tenancy Specification

## Purpose
TBD - created by archiving change toolkit-v1-foundation. Update Purpose after archive.
## Requirements
### Requirement: Each tenant has its own database

Creating a tenant SHALL create its database and bucket and write its access record last, directly
`active`; deleting it SHALL mark the record `deleting` first, then drop the database and the bucket,
then remove the record.

#### Scenario: create then delete
- **WHEN** a library tenant is created and then deleted
- **THEN** its database, its bucket and its access record no longer exist

### Requirement: The start-up sweep finishes interrupted work

At start-up, before serving, the sweep SHALL finish the deletion of every `deleting` tenant and drop
every tenant database and bucket that no access record names, and SHALL never touch anything inside
an `active` tenant.

#### Scenario: a crash during creation
- **WHEN** a tenant database exists without an access record
- **THEN** the next start-up drops it and leaves every active tenant unchanged

