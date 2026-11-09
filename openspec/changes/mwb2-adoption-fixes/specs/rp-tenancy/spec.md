<!-- Capability: rp-tenancy. Change: mwb2-adoption-fixes (#44, DEC-2). -->

## ADDED Requirements

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
- **THEN** the answer is 400 and the root is unchanged
- **AND** a body whose label is "B" is accepted
