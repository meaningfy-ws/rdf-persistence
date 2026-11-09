## ADDED Requirements

### Requirement: The guards catch a required-flag mismatch

The model guards SHALL fail when a generated Python field and the class's generated JSON Schema
disagree on whether the slot is required, naming the class and the slot.

#### Scenario: Python requires what the JSON Schema does not
- **GIVEN** generated output where a class's Python field is required and its JSON Schema leaves the slot optional
- **WHEN** the model guards run
- **THEN** they fail and name the class and the slot
