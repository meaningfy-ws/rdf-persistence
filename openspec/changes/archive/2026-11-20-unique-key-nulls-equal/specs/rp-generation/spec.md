## MODIFIED Requirements

### Requirement: A unique key across aggregates is declared with its scope

A `unique_keys` entry annotated `rp_unique_scope` SHALL be a key across aggregates; any other
`unique_keys` entry SHALL keep its in-aggregate meaning and its generated validators and shapes.
`rp-generate` SHALL fail, naming the class and the key, when a scoped key: has a scope other than
`tenant`; is declared on a class that is neither a tenant-database aggregate root nor an ancestor
of one; names a slot that is not a slot of every such root, or is multivalued, an identifier,
bookkeeping, or holds an owned part; or sets `consider_nulls_inequal: false` with a scope other
than `tenant`, the problem then naming `rp_unique_scope: tenant`. A scoped key with
`rp_unique_scope: tenant` and `consider_nulls_inequal: false` SHALL be accepted. It SHALL also fail
when a `unique_keys` entry on a tenant-database aggregate root has no `rp_unique_scope`. No
validator or shape SHALL be generated for a scoped key.

#### Scenario: a key on an owned part's slot
- **WHEN** the toy schema declares on `Book` a key `isbn_key` with `rp_unique_scope: tenant` over
  the slot `chapters`
- **THEN** `rp-generate` exits with an error naming `Book`, `isbn_key` and `chapters`, and no
  output file changes

#### Scenario: a key slot that is not a slot of the root
- **WHEN** the toy schema declares on `Book` a scoped key over a slot `binding` that `Book` lacks
- **THEN** `rp-generate` exits with an error naming `Book` and `binding`

#### Scenario: a root key without a scope
- **WHEN** the toy schema declares on `Book` a `unique_keys` entry without `rp_unique_scope`
- **THEN** `rp-generate` exits with an error naming `Book` and the key

#### Scenario: absent values counted at tenant scope
- **GIVEN** a scoped key with `rp_unique_scope: tenant` and `consider_nulls_inequal: false`
- **WHEN** `rp-generate` runs
- **THEN** it reports no problem for that key

#### Scenario: an unsupported scope
- **GIVEN** the option on a key whose scope is not `tenant`
- **WHEN** `rp-generate` runs
- **THEN** the hard check refuses it, naming the supported scope

#### Scenario: in-aggregate keys are unchanged
- **WHEN** the toolkit's own schemas are generated after this change
- **THEN** the validator and the shape of `Grant`'s key are as before
