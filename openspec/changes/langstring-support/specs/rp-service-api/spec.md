## ADDED Requirements

<!-- Candidate delta: the EPIC (proposal.md) is shaped, the PLAN is not derived (shaped-not-planned,
     OPEN-1); the requirement may be refined when it is. Decisions: DEC-1, DEC-3, DEC-4. -->

### Requirement: A language tag is never dropped

A value of a language-string slot SHALL keep every language tag through store, read, write and
every document form: plain JSON SHALL show it as a language map, JSON-LD as value objects or a
language map, and an RDF serialisation as tagged literals. A tagged literal found in a slot ranged
`string` SHALL NOT be written back without its tag.

#### Scenario: a read-modify-write keeps the tags
- **GIVEN** a stored book whose `title` is `"Dune"@en` and `"Dune"@fr`
- **WHEN** it is read, another slot is changed and it is written back
- **THEN** the stored graph still holds `"Dune"@en` and `"Dune"@fr`

#### Scenario: plain JSON of a language-string slot
- **GIVEN** that book
- **WHEN** it is read as plain JSON
- **THEN** `title` is `{"en": "Dune", "fr": "Dune"}`
