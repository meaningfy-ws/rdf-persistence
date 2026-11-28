## ADDED Requirements

<!-- langstring-support stage 2. Decisions: DEC-1, DEC-3, DEC-4; PD-14 to PD-16 (design.md). -->

### Requirement: A language tag is never dropped

A value of a language-string slot SHALL keep every language tag, as given, through store, read,
write and every document form: plain JSON and JSON-LD SHALL show each value as a value object
`{"@value": …, "@language": …}`, a plain-JSON write SHALL accept value objects for it, and an RDF
serialisation SHALL show tagged literals. A write whose value object carries a malformed language
tag SHALL be refused as an invalid body. A read through the mapper (a Python session, a write
guard, the relay) that meets a tagged literal in a slot not ranged `lang_string` SHALL be refused
as stored data that cannot be decoded, naming the class and the slot, and SHALL write nothing, as
SHALL such a read meeting an untagged literal in a language-string slot; the
API's GET of such a value keeps its behaviour. A listing filter `=` or `~` on a language-string
slot SHALL be refused as a bad query.

#### Scenario: a read-modify-write keeps the tags
- **GIVEN** a stored book whose `titles` are `"Dune"@en` and `"Dune"@FR`
- **WHEN** it is read in a session, another slot is changed and it is written back
- **THEN** the stored graph is isomorphic to the original apart from the changed slot, both tags
  kept as given

#### Scenario: every format shows each title with its language
- **GIVEN** that book
- **WHEN** it is read as plain JSON, as JSON-LD and as Turtle
- **THEN** plain JSON and JSON-LD show `titles` as the value objects
  `{"@value": "Dune", "@language": "en"}` and `{"@value": "Dune", "@language": "FR"}`, in any order,
  and Turtle shows `"Dune"@en` and `"Dune"@FR`

#### Scenario: a malformed language tag in a write
- **GIVEN** a plain-JSON or JSON-LD body whose `titles` is `[{"@value": "Dune", "@language": "en\n"}]`
- **WHEN** it is written
- **THEN** it is refused as an invalid body naming `titles`, before anything is stored

#### Scenario: an untagged literal in a language-string slot
- **GIVEN** a stored book whose `titles` holds the untagged `"Dune"`, stored before the slot was a
  language string
- **WHEN** it is read in a session
- **THEN** the read is refused naming `Book` and `titles`, and the store is unchanged

#### Scenario: a plain-JSON write of value objects
- **GIVEN** a plain-JSON body whose `titles` is `[{"@value": "Dune", "@language": "en"}]`
- **WHEN** it is written
- **THEN** the store holds `"Dune"@en`; the same body with `"titles": ["Dune"]` is refused as an
  invalid body

#### Scenario: a tagged literal in a string slot
- **GIVEN** a stored book whose `subtitle`, ranged `string`, holds `"Arrakis"@en`
- **WHEN** it is read in a session, or by a write guard
- **THEN** the read is refused naming `Book` and `subtitle`, and the store is unchanged

#### Scenario: a listing filter on a language-string slot
- **GIVEN** books with `titles`
- **WHEN** they are listed with `?titles=Dune`
- **THEN** the request is refused as a bad query naming `titles`
