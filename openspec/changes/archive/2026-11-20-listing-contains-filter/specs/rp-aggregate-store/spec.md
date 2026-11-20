## MODIFIED Requirements

### Requirement: A session finds aggregates by slot values

A session SHALL return, through `find(cls, **equals)`, the IRIs of the tenant's aggregates of class
`cls` whose slots equal the given values; for a multivalued slot every given value SHALL be
present. A value given as `Contains(text=<text>)` SHALL instead match a case-insensitive
substring of a string-ranged slot, as a listing's `<slot>~=<text>` does. It SHALL never return
aggregates of another tenant or another class, and SHALL raise a clear error for a name that is
not a slot of `cls`, and for a `Contains` on a slot that holds no text or with an empty text.

#### Scenario: one match
- **GIVEN** two `Scan` aggregates in a tenant, one with `file_name` "a" and one with "b"
- **WHEN** the session finds scans with `file_name="a"`
- **THEN** it returns exactly the first scan's IRI

#### Scenario: other tenants and classes stay out
- **GIVEN** a `Scan` with `file_name` "a" in another tenant, and a `Book` with a slot valued "a"
- **WHEN** the session finds scans with `file_name="a"`
- **THEN** neither is returned

#### Scenario: an unknown slot
- **WHEN** the session finds scans with `colour="red"`
- **THEN** it raises an error naming `colour` and `Scan`

#### Scenario: a substring in any case
- **GIVEN** books labelled "Dune" and "Emma"
- **WHEN** the session finds books with `label=Contains(text="DUNE")`
- **THEN** it returns exactly the IRI of "Dune"

#### Scenario: a substring of a slot that holds no text
- **WHEN** the session finds books with `published=Contains(text="19")`
- **THEN** it raises a bad-query error
