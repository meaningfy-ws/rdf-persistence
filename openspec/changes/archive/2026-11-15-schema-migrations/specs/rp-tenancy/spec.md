## MODIFIED Requirements

### Requirement: A restore refuses a dump it cannot trust

The service kit SHALL refuse a dump, with `InvalidBody` and before creating anything, whose format
version or schema id differ from the running service's, whose schema version is absent, is not a
version of the service's migration chain, or differs from the dump's own stamp, whose
schema-stamps graph holds anything but one plain-string stamp per schema at a version of its
chain, whose recorded effective IRI policy differs from the service's, that holds a quad outside
the named graphs the policy mints for a tenant and the schema-stamps graph, whose root, once
migrated to the running version, does not decode or is refused by a root validator, or whose first
two archive members are not the manifest and the N-Quads file. It SHALL also refuse, with
`InvalidBody`, a deployment whose IRI policy glues the tenant id to a letter, a digit or another
variable. A later archive member that is not a blob SHALL be refused with `InvalidBody`, leaving no
tenant as a failed restore does. It SHALL likewise refuse an archive whose blobs are not followed by
the empty `end` member, or that holds any member after `end`, or whose gzip stream does not end
properly, and an archive that holds more than `max_restore_bytes` once decompressed (the member
headers included), refusing it from the header before the member is read.

#### Scenario: an older schema version of the chain
- **GIVEN** a dump whose manifest records schema version 1 and a service at version 2 with the migration from 1 to 2
- **WHEN** the service restores it
- **THEN** the dump is accepted and the new tenant's data follows version 2

#### Scenario: another schema version
- **GIVEN** a dump whose manifest records schema version 1.0.0, which the service's chain does not hold
- **WHEN** a service whose schema is at version 1.1.0 restores it
- **THEN** it is refused with `InvalidBody` naming the versions, and no database, bucket or access record is created

#### Scenario: a schema version outside the chain
- **GIVEN** a dump whose manifest records a schema version the service's chain does not hold, or none
- **WHEN** the service restores it
- **THEN** it is refused with `InvalidBody` naming the version, and no database, bucket or access record is created

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
