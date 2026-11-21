## ADDED Requirements

### Requirement: A collection may nest collections of its own kind

A collection with `nests: true` SHALL accept as members collections of exactly the same collection
class and `member_class`, which may themselves have `nests` false. It SHALL refuse a cycle with
`InvalidBody` naming it, and a save that loses a race which would otherwise store a cycle SHALL be
refused with a conflict. `members(deep=True)` SHALL list the items of the whole tree, without the
nested collections themselves. (The issue's `transitive=True` is written `deep=True`: the existing
flag is kept so that no caller breaks.) A collection whose member class is itself a collection
class SHALL NOT set `nests`. A collection without `nests` SHALL behave as before.

#### Scenario: a nested collection
- **GIVEN** a nesting collection of `Book` holding a book and a nested collection of `Book`
- **WHEN** it is saved
- **THEN** it is accepted, and `members(deep=True)` lists the books of both

#### Scenario: a deep read lists no sub-collections
- **GIVEN** a nesting collection of `Book` holding book b1 and a nested collection S holding book b2
- **WHEN** a session reads its members with `deep=True`
- **THEN** it gets b1 and b2, and not S

#### Scenario: a cycle
- **GIVEN** a collection that would contain itself through a nested one
- **WHEN** it is saved
- **THEN** it is refused with `InvalidBody` naming the cycle

#### Scenario: racing saves
- **GIVEN** two saves read before either commits, one adding collection B to A and one adding A to B
- **WHEN** both commit
- **THEN** one succeeds and the other is refused with a conflict, and no cycle is stored

#### Scenario: a leaf race
- **GIVEN** a save adding collection N, which does not nest, to C, and a racing save that makes N nest and adds C to it, read before either commits
- **WHEN** the racing save commits first and then the other
- **THEN** the second is refused with a conflict naming N, and no cycle is stored

#### Scenario: a hidden level
- **GIVEN** a nesting collection holding a nested collection the reader may not read
- **WHEN** the reader lists the members with `deep=True`
- **THEN** the nested collection is counted once in the hidden count and its members are neither listed nor counted

#### Scenario: another member class
- **GIVEN** a nested collection whose member class is not `Book`
- **WHEN** it is saved
- **THEN** it is refused as a member of the wrong class

#### Scenario: nesting over a collection member class
- **GIVEN** a collection whose member class is itself a collection class
- **WHEN** it is saved with `nests: true`
- **THEN** it is refused with `InvalidBody`
