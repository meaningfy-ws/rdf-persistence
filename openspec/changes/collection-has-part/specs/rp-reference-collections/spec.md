## ADDED Requirements

### Requirement: Collections state their members with dct:hasPart

A reference collection SHALL state each member it names with `dct:hasPart` (slot `has_part`), and
SHALL NOT state `prov:hadMember`. Every collection service (`members`, `collections_of`,
`delete_cascade`, `referrers`) and access counting SHALL read membership through `dct:hasPart`.

#### Scenario: members are stated with dct:hasPart
- **GIVEN** a collection class
- **WHEN** a collection is saved with two members
- **THEN** its graph states `dct:hasPart` twice and no `prov:hadMember`, and `members`,
  `collections_of`, `delete_cascade` and `referrers` find both

#### Scenario: stored collections are migrated
- **GIVEN** a tenant at schema version 2 holding a collection stated with `prov:hadMember`
- **WHEN** the migration to version 3 runs
- **THEN** the collection states `dct:hasPart` for the same members and the services find them
