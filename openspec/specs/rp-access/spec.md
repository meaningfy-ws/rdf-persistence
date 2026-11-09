# rp-access Specification

## Purpose
TBD - created by archiving change toolkit-v1-foundation. Update Purpose after archive.
## Requirements
### Requirement: Access is decided per tenant and per aggregate

Before every handler, the access check SHALL decide the route's action for the caller from: global
roles in the token that the rules allow, Prohibitions, the caller's Permissions on the tenant and on
the aggregate's scope (`graph_iri(root)`), and the role definitions. Denial SHALL win, and anything
not permitted SHALL be denied.

#### Scenario: a reader may not modify
- **WHEN** a principal granted `reader` in a library sends a modify on one of its books
- **THEN** the answer is 403 and the book is unchanged

#### Scenario: a permission on one aggregate only
- **WHEN** a principal holds a Permission to modify one book and no tenant grant beyond `reader`
- **THEN** it may modify that book and no other

### Requirement: Tenants without a grant stay hidden

The check SHALL answer 404 to a caller with no tenant grant, no permission on the requested
aggregate and no global role the rules allow, and to any caller of a tenant that is not `active`.

#### Scenario: an outsider
- **WHEN** a principal with no grant in a library reads one of its books
- **THEN** the answer is 404

#### Scenario: a tenant being deleted
- **WHEN** a librarian reads a book of a library whose access record is `deleting`
- **THEN** the answer is 404

### Requirement: Deleting a tenant is an administrative act

`DELETE /{tenant_segment}/{t}` SHALL require the `administer` action on the tenant. Deleting an
aggregate of the tenant SHALL keep requiring `delete`. A role that holds `delete` without
`administer` SHALL be able to delete the tenant's aggregates and SHALL NOT be able to delete the
tenant.

#### Scenario: a member deletes an aggregate
- **GIVEN** a caller whose tenant role permits `[read, modify, delete]` and not `administer`
- **WHEN** it deletes an aggregate of the tenant with a current `If-Match`
- **THEN** the answer is 204 and the aggregate is gone

#### Scenario: a member tries to delete the tenant
- **GIVEN** the same caller
- **WHEN** it calls `DELETE` on the tenant
- **THEN** the answer is 403, and the tenant, its database and its bucket remain

#### Scenario: a Prohibition of delete no longer guards the tenant
- **GIVEN** a caller who holds `administer` and a Prohibition of `delete` on the tenant
- **WHEN** it calls `DELETE` on the tenant with a current `If-Match`
- **THEN** the tenant is deleted; a Prohibition of `administer` is what stops it

#### Scenario: an owner deletes the tenant
- **GIVEN** a caller whose tenant role permits `administer`
- **WHEN** it calls `DELETE` on the tenant with a current `If-Match`
- **THEN** the tenant is deleted as before

