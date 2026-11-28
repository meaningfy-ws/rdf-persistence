## MODIFIED Requirements

### Requirement: The toolkit fills the provenance of a command

A command carrying a value for a slot the toolkit fills SHALL be refused before anything is
written. Those slots are its start, end and principal, its generations and invalidations, for a
transition its two states, its comment and the principals it released, and for an assignment the
principals it assigned and the principals it released. The generator SHALL refuse a consumer class
that redefines such a slot,
and a consumer class other than an activity whose slot ranges over a consumer activity class that is
no aggregate root.

#### Scenario: a forged principal
- **WHEN** a command naming another principal as its agent is handled
- **THEN** it is refused and nothing is written
