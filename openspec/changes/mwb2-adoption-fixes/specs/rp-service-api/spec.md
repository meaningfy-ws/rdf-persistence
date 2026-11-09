<!-- Capability: rp-service-api. Change: mwb2-adoption-fixes (#46 DEC-7, #49 DEC-6, #51 DEC-10). -->

## ADDED Requirements

### Requirement: A test can choose the ids the service draws

`install_service` SHALL take an optional `id_source`, through which every tenant and object id is
drawn. Without it, ids SHALL be drawn from a cryptographic generator.

#### Scenario: a drawn tenant id clashes
- **GIVEN** a service installed with an `id_source` that returns an existing tenant's id first and a
  fresh id second
- **WHEN** a tenant is created
- **THEN** it is created with the fresh id, and the existing tenant is unchanged

#### Scenario: no id source
- **GIVEN** a service installed without `id_source`
- **WHEN** two tenants are created
- **THEN** their ids differ and have the length the IRI policy sets

### Requirement: A consumer enforces its own rules on tenant writes

`install_service` SHALL take optional grant validators and root validators. Grant validators SHALL
run on every replacement of a tenant's grant set; root validators SHALL run when a tenant is created
(the creator, who gets the first grant, is the caller), its root is replaced or it is renamed. Each SHALL run before the write; a validator that raises
`InvalidBody` SHALL refuse the write with a 422 problem and nothing SHALL be written. Two writes at
one version SHALL NOT both succeed.

#### Scenario: the last owner is kept
- **GIVEN** a grant validator that refuses a grant set with no `owner`
- **WHEN** an administrator replaces the grants with a set that has no `owner`
- **THEN** the answer is 422, and the record keeps its grants and its version

#### Scenario: two concurrent removals of two owners
- **GIVEN** a tenant with two owners at version `v1`, and that validator
- **WHEN** two grant writes at `v1` each remove a different owner
- **THEN** one succeeds and the other gets 409, and an owner remains

#### Scenario: a root rule on create
- **GIVEN** a root validator that refuses an end date before the start date
- **WHEN** a tenant is created with such a root
- **THEN** the answer is 422, and no database, bucket or access record exists for it

### Requirement: Reads tell the caller what it may do

A read of a tenant's root or of an aggregate SHALL answer an `Allowed-Actions` header listing,
from `read, modify, delete, administer` in that order, the actions the routes on what it read
would allow the caller: on a tenant, `delete` SHALL be listed only when the caller may
`administer` (deleting a tenant needs `administer`); on an aggregate, `administer` SHALL NOT be
listed. Each item of the tenant listing SHALL carry the tenant's list in `allowed_actions`. A
refused read SHALL carry no such header.

#### Scenario: a member reads the tenant and a book
- **GIVEN** a caller whose tenant role permits `read`, `modify` and `delete`
- **WHEN** it reads the tenant and then one of its books
- **THEN** the tenant's `Allowed-Actions` is `read, modify` and the book's is `read, modify, delete`
- **AND** the tenant's item in the listing has `allowed_actions` `[read, modify]`

#### Scenario: a librarian reads the tenant
- **GIVEN** a caller whose tenant role permits all four actions
- **WHEN** it reads the tenant
- **THEN** `Allowed-Actions` is `read, modify, delete, administer`
