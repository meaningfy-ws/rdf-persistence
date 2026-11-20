## ADDED Requirements

### Requirement: Listings filter by a case-insensitive substring

A listing SHALL accept `<slot>~=<text>` on a string-ranged slot, and `Session.find` SHALL accept
`Contains(<text>)`, matching a case-insensitive substring, combinable with other filters, with
paging and totals unchanged. On a non-string slot it SHALL answer `400 bad-query`.

#### Scenario: a substring in any case
- **GIVEN** books "Dune", "Children of Dune" and "Emma"
- **WHEN** listing `title~=DUNE`
- **THEN** two books are returned, total 2

#### Scenario: a non-string slot
- **WHEN** listing `year~=19`
- **THEN** the answer is 400 `bad-query`

#### Scenario: combined filters
- **WHEN** listing `title~=dune&author=<iri>`
- **THEN** both filters apply
