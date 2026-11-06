## ADDED Requirements

### Requirement: Protected properties are hidden from callers without access

When an access module protects a property of an aggregate type, the service SHALL leave that
property out of every representation it returns to a caller without access to it, plain JSON,
JSON-LD, Turtle and listings alike, and SHALL refuse a listing filter on that property for that caller.

#### Scenario: a reader cannot see a protected slot
- **GIVEN** the toy library protects a book slot so only a librarian reads it, and a stored book with that slot set
- **WHEN** a reader gets the book as JSON, as JSON-LD and as Turtle
- **THEN** no representation holds the slot or its value, and a librarian's representation holds it

#### Scenario: a filter would reveal a protected value
- **GIVEN** the same protected slot
- **WHEN** a reader lists books filtered on that slot
- **THEN** the request is refused and reveals no value

### Requirement: Writes to protected properties are checked

A write that adds, changes or removes a protected property SHALL be refused for a caller without
write access to that property, and SHALL leave the aggregate unchanged.

#### Scenario: a caller without access changes a protected slot
- **GIVEN** a caller who may modify books but not the protected slot
- **WHEN** the caller replaces a book with a new value in that slot
- **THEN** the write is refused and the stored book is unchanged

### Requirement: An alternative decision engine agrees with the in-process check

If a second decision engine is configured, it SHALL give the same decision as the in-process check
for every caller, action and target of the toy library's permission matrix, fed only from the ODRL
records.

#### Scenario: the permission matrix under both engines
- **GIVEN** the toy library's roles, grants and prohibitions
- **WHEN** every cell of the permission matrix is decided by both engines
- **THEN** every decision is equal
