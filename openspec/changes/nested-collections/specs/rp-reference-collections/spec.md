## ADDED Requirements

### Requirement: A collection may nest collections of its own kind

A collection with `nests: true` SHALL accept as members collections of the same collection class
and `member_class`, SHALL refuse a cycle with `InvalidBody` naming it, and SHALL list the items of
the whole tree through `members(transitive=True)`. A collection without `nests` SHALL behave as
before.

#### Scenario: a nested collection
- **GIVEN** a nesting collection of `Book` holding a book and a nested collection of `Book`
- **WHEN** it is saved
- **THEN** it is accepted, and `members(transitive=True)` lists the books of both

#### Scenario: a cycle
- **GIVEN** a collection that would contain itself through a nested one
- **WHEN** it is saved
- **THEN** it is refused with `InvalidBody` naming the cycle

#### Scenario: another member class
- **GIVEN** a nested collection whose member class is not `Book`
- **WHEN** it is saved
- **THEN** it is refused as a member of the wrong class
