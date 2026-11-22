## ADDED Requirements

### Requirement: Slots that share an IRI are locked apart

The lock SHALL keep each slot of a class, also when two slots share an IRI, and the comparison
SHALL pair them: a slot added on an IRI already locked SHALL be a slot added, never a change of
the other slot's range.

#### Scenario: a business identifier beside the identifier
- **GIVEN** a class locked with its identifier on `dcterms:identifier`
- **WHEN** the class gains an optional business slot on `dcterms:identifier`
- **THEN** the comparison reports one slot added, and generation succeeds without a new version
