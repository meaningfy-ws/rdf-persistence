<!-- Capability: rp-access. Change: mwb2-adoption-fixes (#43, DEC-1). -->

## ADDED Requirements

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
