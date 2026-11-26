## ADDED Requirements

<!-- Conditional on the seed spike passing (DEC-5, PD-6): task 2.2 deletes this delta on a fail. -->

### Requirement: The full local run also records the test selection data

Run locally, `make test` (and so `make check-all`) SHALL run its unit, feature and generator lanes
inside one seed run that records the test selection data into one file and swaps it in once, after
the last lane, with the seed's commit; a lane run alone SHALL NOT record. Under `CI`, `make test`
SHALL NOT record. A lane that fails SHALL leave the earlier selection data in place.

#### Scenario: check-all passes
- **GIVEN** a worktree on commit C
- **WHEN** `make check-all` passes there
- **THEN** the selection data holds the unit, feature and generator tests' run and the recorded
  seed commit is C, so the next stage needs no `make test-seed` on C

#### Scenario: a lane fails
- **GIVEN** earlier selection data recorded on commit B
- **WHEN** `make check-all` fails in its feature lane
- **THEN** the selection data and the recorded commit B stay as they were

#### Scenario: a lane alone
- **WHEN** `make test-unit` runs on its own
- **THEN** it records no selection data
