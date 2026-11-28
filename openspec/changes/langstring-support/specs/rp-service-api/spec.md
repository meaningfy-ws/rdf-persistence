## ADDED Requirements

<!-- Candidate delta: the EPIC (proposal.md) is shaped, the PLAN is not derived (shaped-not-planned,
     OPEN-1); the requirement may be refined when it is. Decisions: DEC-1, DEC-3, DEC-4. -->

### Requirement: A language tag is never dropped

A value of a language-string slot SHALL keep every language tag through store, read, write and
every document form: plain JSON and JSON-LD SHALL show each value as a value object
`{"@value": …, "@language": …}`, and an RDF serialisation as tagged literals. A tagged literal
found in a slot ranged `string` SHALL be refused, naming the slot, never written back without its
tag.

#### Scenario: a read-modify-write keeps the tags
- **GIVEN** a stored book whose `title` is `"Dune"@en` and `"Dune"@fr`
- **WHEN** it is read, another slot is changed and it is written back
- **THEN** the stored graph still holds `"Dune"@en` and `"Dune"@fr`

#### Scenario: plain JSON of a language-string slot
- **GIVEN** that book
- **WHEN** it is read as plain JSON
- **THEN** `title` is `[{"@value": "Dune", "@language": "en"}, {"@value": "Dune", "@language": "fr"}]`

#### Scenario: a tagged literal in a string slot
- **GIVEN** a stored book whose `subtitle`, ranged `string`, holds `"Arrakis"@en`
- **WHEN** it is read
- **THEN** the read is refused naming `subtitle`, and the store is unchanged
