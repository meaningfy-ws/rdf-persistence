## ADDED Requirements

### Requirement: A fallback path counts only if it changed since the seed

The testkit's seed SHALL record, beside the selection data it swaps in, the commit it ran on, and
SHALL remove that record when it swaps in data whose commit it cannot read or whose tracked files
differed from that commit when the seed started. When the selection
data is sound and a seed commit is recorded and readable, the changed-tests planner SHALL keep a
changed path's fallback reasons only if that path differs between the seed's commit and the
working tree, and SHALL name every path it set aside in a hint; a path that differs from the
seed's commit but not from the base SHALL still be classified, and its fallback reasons SHALL
count. Otherwise the planner SHALL plan
as it did without the record.

#### Scenario: a shared file changed before the seed
- **GIVEN** a branch whose `Makefile` changed, and a sound seed taken after that change
- **WHEN** a task changes one source file and runs the planner
- **THEN** the planner runs testmon's selection, does not fall back, and hints that `Makefile`
  is unchanged since the seed

#### Scenario: a shared file changed after the seed
- **GIVEN** a sound seed, then a change to `Makefile`
- **WHEN** the planner runs
- **THEN** it falls back, as it does without a seed commit

#### Scenario: a shared file reverted after the seed
- **GIVEN** a branch that changed `Makefile`, a sound seed taken then, and `Makefile` since
  reverted to the base's content
- **WHEN** the planner runs
- **THEN** it falls back, because the data was recorded under a `Makefile` the worktree no longer
  has

#### Scenario: no seed commit
- **GIVEN** selection data with no recorded commit, or a commit git cannot read
- **WHEN** the planner runs
- **THEN** it plans exactly as it does without the record

#### Scenario: a seed on a dirty tree
- **GIVEN** a tracked file with uncommitted changes
- **WHEN** a seed runs and finishes
- **THEN** its data is swapped in with no recorded commit, so the planner plans as it does without
  the record

#### Scenario: a seed that did not finish
- **GIVEN** a recorded seed commit C
- **WHEN** a later seed is interrupted before its run finishes
- **THEN** the selection data and the recorded commit C both stay as they were
