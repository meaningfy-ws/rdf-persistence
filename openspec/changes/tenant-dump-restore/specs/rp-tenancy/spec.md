## ADDED Requirements

### Requirement: A tenant can be dumped and restored into a new tenant

The service kit SHALL write a tenant as one archive holding a manifest, every named graph of the
tenant's database as N-Quads, and every blob of its bucket. It SHALL restore such an archive only
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
restore does.

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
