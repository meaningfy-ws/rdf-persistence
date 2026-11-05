Capability: rp-access. Source: EPIC `toolkit-v1-foundation`; architecture `access-control.adoc` (N-8,
D-4, D-5).

## ADDED Requirements

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

A caller with no grant in a tenant, and no global role the rules allow, or any caller of a tenant
that is not `active`, SHALL get 404.

#### Scenario: an outsider
- **WHEN** a principal with no grant in a library reads one of its books
- **THEN** the answer is 404
