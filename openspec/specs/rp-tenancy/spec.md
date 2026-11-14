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

### Requirement: Orphans inside a live tenant are removed

A sweep of an `active` tenant SHALL find every loaded graph that no registry entry owns and every
blob that no graph of the tenant names in `rp:fileKey`, each older than a grace period (default one
hour). It SHALL remove the loaded graphs only when asked to remove them, and the blobs only when
asked, separately, to remove blobs; by default it is a dry run. It SHALL never remove a loaded
graph or blob that a committed aggregate names, nor one younger than the grace period, and SHALL
never touch the tenant's `meta`, `registry`, access or aggregate graphs, nor another tenant. A
graph loaded for the tenant root SHALL be treated like one loaded for any aggregate. It SHALL return a report listing what it found and what it removed.

#### Scenario: an uncommitted loaded graph is swept
- **GIVEN** an active library tenant with a graph loaded for a book two hours ago and never named by a commit
- **WHEN** the live-tenant sweep runs with removal of loaded graphs
- **THEN** the loaded graph no longer exists, the report lists it, and every committed book and its loaded graphs are unchanged

#### Scenario: a blob of a removed aggregate is swept
- **GIVEN** an active library tenant where a scan was stored two hours ago and its aggregate then removed through the session
- **WHEN** the live-tenant sweep runs with removal of blobs
- **THEN** the scan's blob no longer exists and the blobs of every stored scan are byte for byte unchanged

#### Scenario: blobs stay unless their removal is asked for
- **GIVEN** an active tenant with an old orphan loaded graph and an old orphan blob
- **WHEN** the live-tenant sweep runs with removal of loaded graphs only
- **THEN** the loaded graph is gone, the blob still exists, and the report says the blob was not removed

#### Scenario: work in flight is kept
- **GIVEN** a graph loaded for a book five minutes ago whose commit has not yet run
- **WHEN** the live-tenant sweep runs with removal
- **THEN** the graph is kept and the commit that names it succeeds

#### Scenario: a dry run changes nothing
- **GIVEN** an active tenant with an old orphan loaded graph and an old orphan blob
- **WHEN** the live-tenant sweep runs without removal
- **THEN** the report lists both as not removed, and both still exist

#### Scenario: a tenant being deleted is not swept
- **GIVEN** a tenant in the deleting state
- **WHEN** the live-tenant sweep runs on it
- **THEN** it is refused as a conflict and nothing is removed

#### Scenario: a root load is swept only when no commit owns it
- **GIVEN** an active tenant with two graphs loaded for its root two hours ago, one committed with the root and one never committed
- **WHEN** the live-tenant sweep runs with removal of loaded graphs
- **THEN** the uncommitted graph is gone and listed in the report, and the committed one still exists and is still listed by the root

### Requirement: A file aggregate can be removed with its blobs

The service kit SHALL offer a removal of an aggregate at a version that, after the aggregate is
removed, deletes from the tenant's bucket every blob the aggregate named in `rp:fileKey` that no
other graph of the tenant still names. A stale version SHALL be refused with nothing changed. A blob
that cannot be deleted SHALL be logged and left for the live-tenant sweep; the removal of the
aggregate SHALL still succeed.

#### Scenario: a scan's blob goes with it
- **GIVEN** a stored scan whose file key names a blob
- **WHEN** the consumer's delete route removes the scan with its files
- **THEN** the scan and its blob no longer exist

#### Scenario: a shared blob stays
- **GIVEN** two scans whose file keys name the same blob
- **WHEN** one scan is removed with its files
- **THEN** the blob still exists

#### Scenario: the object store fails
- **GIVEN** a stored scan and an object store that fails on delete
- **WHEN** the scan is removed with its files
- **THEN** the scan no longer exists, the blob remains, and the failure is logged

### Requirement: A tenant can be dumped and restored into a new tenant

The service kit SHALL write a tenant as one archive holding a manifest, every named graph of the
tenant's database as N-Quads, and every blob of its bucket (format version 1), and SHALL end the archive with an empty regular member
named `end`. It SHALL restore such an archive only
into a new tenant, minted as on create, whose IRIs carry the new tenant id in place of the source
tenant id, whose access record grants only the restorer the creator role, and whose aggregates,
loaded graphs and blobs read back as the original's did. It SHALL write the new access record last.

#### Scenario: a restored tenant answers like the original
- **GIVEN** a library tenant with books, a graph loaded for a book, a graph loaded for its root and a scan
- **WHEN** it is dumped and the dump is restored by another principal
- **THEN** a new tenant exists with a new IRI and the original's label
- **AND** every book reads back with the same slot values under an IRI that carries the new tenant id
- **AND** both loaded graphs are listed by their owners and hold the original's triples
- **AND** the scan's bytes read back from the new tenant's bucket byte for byte

#### Scenario: the restored tenant accepts writes
- **GIVEN** a tenant restored from a dump
- **WHEN** one of its books is replaced at the version it read
- **THEN** the replace succeeds, and the original tenant's book is unchanged

#### Scenario: only the restorer is granted
- **GIVEN** a tenant whose access record grants several principals
- **WHEN** it is dumped and restored by principal P
- **THEN** the new tenant's access record grants P the creator role and no one else

#### Scenario: a flat IRI policy
- **GIVEN** a deployment whose aggregate, part and loaded-graph templates are `{base}{tenant_id}/{type}/{id}`
- **WHEN** a tenant is dumped and restored
- **THEN** every aggregate, part and loaded graph of the new tenant carries the new tenant id and is accepted by the policy

#### Scenario: literals are kept as they are
- **GIVEN** a book whose title is a literal holding the source tenant's IRI
- **WHEN** the tenant is dumped and restored
- **THEN** the restored book's title is the same literal

### Requirement: A restore refuses a dump it cannot trust

The service kit SHALL refuse a dump, with `InvalidBody` and before creating anything, whose format
version, schema id or schema version differ from the running service's, whose recorded effective IRI
policy differs from the service's, that holds a quad outside the named graphs the policy mints for a
tenant, whose root does not decode or is refused by a root validator, or whose first two archive
members are not the manifest and the N-Quads file. It SHALL also refuse, with `InvalidBody`, a
deployment whose IRI policy glues the tenant id to a letter, a digit or another variable. A later
archive member that is not a blob SHALL be refused with `InvalidBody`, leaving no tenant as a failed
restore does. It SHALL likewise refuse an archive whose blobs are not followed by the empty `end`
member, or that holds any member after `end`, or whose gzip stream does not end properly, and an
archive that holds more than `max_restore_bytes` once decompressed (the member headers included),
refusing it from the header before the member is read.

#### Scenario: another schema version
- **GIVEN** a dump whose manifest records schema version 1.0.0
- **WHEN** a service whose schema is at version 1.1.0 restores it
- **THEN** it is refused with `InvalidBody` naming the versions, and no database, bucket or access record is created

#### Scenario: another IRI policy
- **GIVEN** a dump made under object ids of 13 characters
- **WHEN** a service whose policy draws object ids of 12 characters restores it
- **THEN** it is refused naming `object_id.length`, and nothing is created

#### Scenario: a graph the policy does not mint
- **GIVEN** a dump with a quad in the graph `http://elsewhere.example/g`
- **WHEN** it is restored
- **THEN** it is refused and nothing is created

#### Scenario: an archive cut short or with a member after the end
- **GIVEN** a dump archive that stops after its blobs without the `end` member, or that holds a member after `end`
- **WHEN** it is restored
- **THEN** it is refused with `InvalidBody` and no access record is written
- **AND** the new database and bucket the blobs were written to are dropped, as a failed restore does

#### Scenario: an archive past the restore budget
- **GIVEN** a service whose `max_restore_bytes` is smaller than a dump archive holds once decompressed
- **WHEN** the archive is restored
- **THEN** it is refused with `InvalidBody` naming the byte limit, and no access record is written
- **AND** when the overflow is met before the blobs, no database or bucket is created

### Requirement: Dumping a tenant needs it active

Dumping SHALL answer `NotFound` for a tenant without an access record and `Conflict` for a tenant
being deleted, and SHALL change nothing in the tenant.

#### Scenario: a tenant being deleted
- **GIVEN** a tenant in the deleting state
- **WHEN** it is dumped
- **THEN** the dump is refused as a conflict and no archive is written

### Requirement: A restore that fails leaves no tenant

A restore that fails after creating the new database or bucket SHALL leave no access record, SHALL
try to drop that database and bucket, and SHALL leave anything it could not drop to the start-up
sweep.

#### Scenario: the new database vanishes before the access record
- **GIVEN** a restore whose new database is dropped by a start-up sweep after its blobs are written
- **WHEN** the restore is about to write the access record
- **THEN** it fails, writes no access record, and the new bucket is gone

#### Scenario: the store fails during the import
- **GIVEN** a store that fails while the quads are imported
- **WHEN** a dump is restored
- **THEN** the restore raises the store's error, no access record exists for a new tenant, and the new database and bucket are gone

### Requirement: The application keeps its own aggregates outside any tenant

The service kit SHALL store the aggregates of every class the schema annotates `database:
application` in one application database, created at start-up when the schema has such a class, and
SHALL offer a session on it with the same reads, versioned writes and loaded graphs as a tenant
session, and SHALL mint the IRI of a new application aggregate for its class. A class SHALL be
application-level when it, or a class it descends from by `is_a`, carries the annotation; a
mixin's annotation SHALL not count. A session SHALL never store such an aggregate in a tenant
database, nor a tenant class in the application database, and SHALL never write an access record
through an application session: a tenant session SHALL refuse a root typed as an application
class, and an application session SHALL refuse a root not typed as one, with `InvalidIri` and
before anything is sent. The application session SHALL also refuse the application IRI itself and
the IRI of an access record as the IRI of an aggregate. Restoring a tenant dump SHALL refuse, with
`InvalidBody` and before anything is created, a dump that holds an object typed as an application
class. Generation SHALL fail for an application class that is the tenant root, is
owned, is not an aggregate root, is a stored file, or shares its class IRI with a root of another
database, and for a mixin that carries the annotation.

#### Scenario: an application aggregate is not in any tenant
- **GIVEN** an application aggregate and a tenant
- **WHEN** the tenant's aggregates are listed and the application's aggregate is read through an application session
- **THEN** the listing does not include it and the read returns it

#### Scenario: application writes are versioned
- **GIVEN** an application aggregate at version v1
- **WHEN** two application sessions replace it at v1
- **THEN** the first succeeds and the second is refused as a conflict

#### Scenario: a class in the wrong space
- **GIVEN** `Book` is a tenant class and `Template` an application class
- **WHEN** a `Book` is committed through an application session, or a `Template` through a tenant session
- **THEN** the session raises `InvalidIri` and nothing is written

#### Scenario: a subclass of an application class
- **GIVEN** `ReportTemplate` is a `Template` and carries no annotation of its own
- **WHEN** a `ReportTemplate` is committed through an application session
- **THEN** it is stored in the application database

#### Scenario: a root with no class
- **GIVEN** triples that give their root no type
- **WHEN** they are added through an application session
- **THEN** the session raises `InvalidIri` and nothing is written

#### Scenario: a class moved to the application after it had data
- **GIVEN** a `Template` stored in a tenant database before the class was annotated `database: application`
- **WHEN** a tenant session reads it, replaces it, and removes it
- **THEN** the read returns it, the replace raises `InvalidIri`, and the remove succeeds

#### Scenario: the sweep leaves the application database alone
- **GIVEN** an application database with aggregates and no access record naming it
- **WHEN** the start-up sweep runs
- **THEN** the application database and its aggregates are unchanged

#### Scenario: a schema without application classes
- **GIVEN** a schema with no class annotated `database: application`
- **WHEN** the start-up step that ensures the application database runs
- **THEN** no application database is created

#### Scenario: a dump that carries an application class
- **GIVEN** a tenant dump in which an aggregate is typed as the application class `Template`
- **WHEN** it is restored
- **THEN** the restore is refused with `InvalidBody` and no tenant is created

#### Scenario: the application IRI is not an aggregate
- **GIVEN** an application session
- **WHEN** a `Template` is added at the application IRI itself, or at the IRI an access record would have
- **THEN** the session raises `InvalidIri` and nothing is written

