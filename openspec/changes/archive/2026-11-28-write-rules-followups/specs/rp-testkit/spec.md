## MODIFIED Requirements

### Requirement: A rule is unit-tested with the testkit's reader

`rdf_persistence.testkit` SHALL offer `FakeAggregateReader`, an in-memory `AggregateReader` seeded
with generated aggregates and the IRIs the writer may not read. It SHALL answer `classes_of`,
`aggregate` and `find` as the real reader does for the aggregates seeded, leave out the unreadable
ones, refuse what the real reader refuses with the same error and in the same order (a dotted
keyword included, with `BadQuery`), and record each call with its arguments in order; a `Contains`
value is its one limit (`NotImplementedError`). `rdf_persistence.testkit.reader_conformance`
SHALL hold the cases of that contract, each taking a reader seeded the same way, so that one test
runs them against the fake and the real reader.

#### Scenario: a rule under unit test
- **GIVEN** a validator under unit test and a `FakeAggregateReader` seeded with two books, one unreadable by the writer
- **WHEN** the validator is called with it
- **THEN** the rule sees only the readable book, and the test asserts the reader calls the rule made, with no consumer-side stub

#### Scenario: the fake and the real reader agree
- **GIVEN** the reader conformance cases
- **WHEN** they run against the fake and against the real reader over the same seeded aggregates
- **THEN** every case passes for both

#### Scenario: a dotted keyword (S4)
- **WHEN** a rule calls `find` on either reader with a dotted keyword such as `**{"holder.name": "x"}`
- **THEN** it raises `BadQuery`, before any query, and the conformance kit holds the case
