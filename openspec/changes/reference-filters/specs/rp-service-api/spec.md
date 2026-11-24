## ADDED Requirements

### Requirement: A listing filters through references

A listing SHALL accept a filter whose name is a path, `<reference>.<slot>` (equality) or
`<reference>.<slot>~` (contains), crossing at most three references, each a listable reference to
an aggregate root in the listing's database, the next segment being a listable slot of its range
class. It SHALL return the aggregates for which some referenced aggregate, read in its own graph,
satisfies the last segment, paged and counted like any listing; a crossed aggregate hidden from
the caller by a read Prohibition SHALL NOT satisfy it. Each path filter SHALL be satisfied independently. A path that names
an unknown slot, a slot that is not a reference, more than three references or an empty segment,
and a path given to `absent` or `sort`, SHALL be refused as a bad query.

#### Scenario: one reference
- **GIVEN** two books, one written by an author labelled "Frank Herbert" and one by another author
- **WHEN** a caller lists books with `written_by.label=Frank Herbert`
- **THEN** only the first book is returned and the total is 1

#### Scenario: two references
- **GIVEN** a book whose sequel_of points to a book written by an author labelled "Frank Herbert"
- **WHEN** a caller lists books with `sequel_of.written_by.label=Frank Herbert`
- **THEN** that book is returned

#### Scenario: a multivalued reference is listed once
- **GIVEN** a display featuring two books, both written by author A
- **WHEN** a caller lists displays with `features.written_by=<A's IRI>`
- **THEN** the display is returned once and the total counts it once

#### Scenario: a hidden referenced aggregate
- **GIVEN** a book written by an author the caller has a read Prohibition on
- **WHEN** the caller lists books with `written_by.label=<that author's label>`
- **THEN** the book is not returned and the total does not count it

#### Scenario: a statement in another graph
- **GIVEN** an aggregate whose own graph states a label for an author, which the author's graph does not hold
- **WHEN** a caller lists books with `written_by.label=<that label>`
- **THEN** no book is returned

#### Scenario: a path that is not one
- **WHEN** a caller lists books with `isbn.x=1`, `nosuch.label=x`, `written_by..label=x` or a path of four references
- **THEN** the answer is the 400 bad-query problem
