## ADDED Requirements

### Requirement: Listings filter by a case-insensitive substring

A listing SHALL accept `<slot>~=<text>` on a string-ranged slot, and `Session.find` SHALL accept
`Contains(text=<text>)`, matching a case-insensitive substring, combinable with other filters,
with paging and totals unchanged; an aggregate SHALL be listed and counted once however many of
its values match. On a non-string slot, or with an empty text, it SHALL answer `400 bad-query`.
The OpenAPI document SHALL show a `<slot>~` query parameter for each string-ranged slot of a
listed type, and for no other slot.

#### Scenario: a substring in any case
- **GIVEN** books labelled "Dune", "Children of Dune" and "Emma"
- **WHEN** listing `label~=DUNE`
- **THEN** two books are returned, total 2

#### Scenario: a non-string slot
- **WHEN** listing `published~=19`
- **THEN** the answer is 400 `bad-query`

#### Scenario: combined filters
- **GIVEN** "Dune" of genre fiction and "Children of Dune" of genre nonfiction
- **WHEN** listing `label~=dune&genre=fiction`
- **THEN** only "Dune" is returned, total 1

#### Scenario: an empty text
- **WHEN** listing `label~=`
- **THEN** the answer is 400 `bad-query`

#### Scenario: an item matching on several values is listed once
- **GIVEN** books whose authors are "Herbert"; "Austen"; "Joyce" and "Herbert"; and "Morrison"
- **WHEN** listing `authors~=E&limit=2`
- **THEN** the page holds two distinct books and the total is 3

#### Scenario: the contract shows a contains parameter per string slot
- **WHEN** the OpenAPI document of the books listing is read
- **THEN** it has `label~`, `description~`, `isbn~` and `authors~` parameters, and no `published~`
  or `genre~`
