## ADDED Requirements

<!-- Candidate delta: the EPIC (proposal.md) is shaped, the PLAN is not derived yet; the
     requirement may be refined when it is. Decisions: DEC-2, DEC-5, DEC-6, DEC-8, DEC-9. -->

### Requirement: A tenant's history can be harvested as a Linked Data Event Stream

When the consumer turns the view on, each tenant SHALL publish its provenance graph as a Linked
Data Event Stream (LDES 1.0.0) over TREE pages, under the toolkit's reserved prefix. Each member
SHALL be one aggregate's change in one activity, typed as created, updated or removed, naming the
aggregate, its class, its version token, the activity and the time, and never the aggregate's
content; a member's IRI SHALL be the same on every read. Pages SHALL hold the members of one UTC
hour, reached from one node per UTC day. A page SHALL list a member only when the caller may read
its aggregate, by the same rule as server-sent events, and every route SHALL need `read` on the
tenant. A page whose hour ended longer ago than the settle delay SHALL be marked immutable. With the
view off, the routes SHALL NOT exist; server-sent events SHALL behave as before either way.

#### Scenario: a replace is one update
- **GIVEN** the view on and a stored book
- **WHEN** the book is replaced and a harvester reads the page of that hour
- **THEN** the page holds one updated member naming the book and its new version token

#### Scenario: a hidden aggregate
- **GIVEN** a reader with a Prohibition of `read` on one book
- **WHEN** that book and another are replaced in one transaction and the reader reads the page
- **THEN** the page holds the other book's member only

#### Scenario: a settled page
- **GIVEN** a page whose hour ended longer ago than the settle delay
- **WHEN** a harvester reads it
- **THEN** it is marked `ldes:immutable` and served with `Cache-Control` `immutable`

#### Scenario: the view is off
- **GIVEN** a service installed without the view
- **WHEN** a caller requests the tenant's `rp-ldes` route
- **THEN** it is answered as an unknown route
