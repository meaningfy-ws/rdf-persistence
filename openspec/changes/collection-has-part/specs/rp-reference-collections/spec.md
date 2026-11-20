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

#### Scenario: a dump at version 2 is restored
- **GIVEN** a dump of a tenant taken at the toolkit's schema version 2, holding a collection stated with `prov:hadMember`
- **WHEN** it is restored into a service at version 3
- **THEN** the new tenant's collection states `dct:hasPart` for the same members and `members` lists them

## MODIFIED Requirements

### Requirement: A reference collection holds typed references it does not own

The metamodel SHALL provide a reference collection class (a `dcmitype:Collection`) that an
application uses as an aggregate root or mixes into one. A collection SHALL name the class of its
members and SHALL hold references (`dct:hasPart`) to aggregates of the same tenant, never their
triples. Saving a collection with a member of another class, or with an IRI the IRI policy does
not mint for the tenant, SHALL be refused and nothing SHALL be stored.

#### Scenario: a shelf of books
- **WHEN** a session saves a collection of class `Book` naming two stored books
- **THEN** reading the collection returns both IRIs, and each book's graph is unchanged

#### Scenario: a member of the wrong class
- **WHEN** a session saves a collection of class `Book` naming a shelf
- **THEN** the save is refused as invalid and the collection is not stored
