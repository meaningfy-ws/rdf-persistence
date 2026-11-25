## ADDED Requirements

### Requirement: A membership rule names slots of the member class only

A membership rule's equality SHALL name a slot of the member class itself. An equality whose slot
is a path through references (`<reference>.<slot>`) SHALL be refused when the collection is
written, and a stored rule holding one SHALL be reported as invalid stored data, so that no path
condition reaches `matches` or the commit guard.

#### Scenario: a rule through a reference
- **WHEN** a caller writes a collection whose membership rule has the equality `written_by.label = Frank Herbert`
- **THEN** the write is refused as an invalid body and nothing is stored
