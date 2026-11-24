## ADDED Requirements

### Requirement: The aggregate strategy draws what the class accepts

`aggregate(conformance, class_name)` SHALL draw each slot from the class's induced slot, its
`slot_usage` applied: `equals_string` SHALL give that exact value, `equals_string_in` one of its
values, and a slot made `multivalued` by `slot_usage` a list.

#### Scenario: a reference collection's member class
- **GIVEN** a class with `slot_usage: {member_class: {equals_string: Book}}`
- **WHEN** the strategy draws it
- **THEN** `member_class` is `Book` and the round trip passes

#### Scenario: a slot made multivalued by the class
- **GIVEN** a class with `slot_usage: {holds: {multivalued: true}}` on a single-valued slot
- **WHEN** the strategy draws it
- **THEN** `holds` is a list and the round trip passes
