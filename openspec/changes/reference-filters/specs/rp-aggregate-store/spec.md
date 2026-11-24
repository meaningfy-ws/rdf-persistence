## ADDED Requirements

### Requirement: find filters through references

`Session.find` SHALL accept a keyword whose name is a path, `<reference>.<slot>`, with the same
meaning and refusals as a listing's path filter, and SHALL ignore prohibitions as it does for
every filter.

#### Scenario: a dotted keyword
- **GIVEN** a book written by an author labelled "Frank Herbert"
- **WHEN** a service calls `find(Book, **{"written_by.label": "Frank Herbert"})`
- **THEN** the book's IRI is returned
