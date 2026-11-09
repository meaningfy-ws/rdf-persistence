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

### Requirement: A tenant has one label

Renaming a tenant SHALL change the label of both its access record and its root object. The
rename SHALL check the record's version before it writes anything, write the root first and the
record last. Replacing the tenant's root SHALL be refused as an invalid body when the body's
label differs from the access record's.

#### Scenario: a rename reaches the root
- **GIVEN** a tenant created with label "A"
- **WHEN** it is renamed to "B"
- **THEN** both its access record and its root object read "B"

#### Scenario: a stale rename changes nothing
- **GIVEN** a tenant whose access record has moved past version `v1`
- **WHEN** it is renamed with `If-Match: v1`
- **THEN** the rename is refused as a conflict, and the record and the root keep their label

#### Scenario: a rename that stopped halfway is retried
- **GIVEN** a rename to "B" whose root write succeeded and whose record write failed
- **WHEN** the same rename is retried with the same `If-Match`
- **THEN** both the record and the root read "B"

#### Scenario: the record moved during a rename
- **GIVEN** a rename to "B" whose root write succeeded, and the access record changed by another
  request before the record write
- **WHEN** the rename writes the record
- **THEN** it is refused as a conflict; after re-reading the record's version, the same rename
  leaves both the record and the root at "B"

#### Scenario: the root cannot change the label
- **GIVEN** a tenant labelled "B"
- **WHEN** its root is replaced with a body whose label is "C"
- **THEN** the answer is 422 and the root is unchanged
- **AND** a body whose label is "B" is accepted

### Requirement: Any reader can learn the record's version

A read of the tenant's root SHALL answer the access record's version in a `Record-ETag` header, in
the form of `ETag`. A rename SHALL accept that version as `If-Match`.

#### Scenario: a member renames the tenant
- **GIVEN** a caller with `read` and `modify` on the tenant and not `administer`
- **WHEN** it reads the tenant's root and renames the tenant with the `Record-ETag` it read
- **THEN** the rename succeeds
- **AND** a rename with an older version is refused as a conflict

