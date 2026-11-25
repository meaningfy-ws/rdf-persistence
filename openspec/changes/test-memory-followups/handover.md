# Hand-over: test-memory-followups, parked during planning

## Done
EPIC shaped (SMALL, DEC-1 to DEC-4); PLAN derived, validated and gated: run 1 8.4, ten gaps folded
in; run 2 8.9, eight slips folded in, accepted under R-0005 (`evidence/clarity-gate.md`). Branch
`docs/plan-test-memory-followups`, no PR.

## Decided since the PLAN
2026-11-25, from a `review-floors` close-out session (`inputs/qa.md` round 2, `inputs/seed.md`
items 5 and 6): DEC-5 / PD-6, the seed spike (tasks 2.1, 2.2; the close is now section 3);
DEC-6 / PD-7, no test run nobody reads. Its docs part is already on `develop` (#398, rule P-0022).
These were added after gate run 2: the PLAN needs a gaps-only gate over DEC-5, DEC-6, PD-6, PD-7
and section 2 before the plan PR. Q1 to Q5 are still open.

## Open
- Parked by the developer on 2026-11-25. rdf-persistence v0.15.0 shipped without it.
- The developer's answers to Q1 to Q5 (`inputs/qa.md`); the PLAN is shaped on the recommended ones.
- DEC-8 of agent-test-control (task 3.2 here) can be measured independently once sessions run on
  v0.15.0 / develop.

## Next
Get Q1 to Q5 answered (a changed answer re-opens its DEC and a gaps-only gate), open and merge the
plan PR, then deliver stage 1 (tasks 1.1 to 1.3 and the spike 2.1 in parallel, then 2.2, then
3.1). Task 3.2 (DEC-8) waits for the
paused sessions to run on `develop`. Read first: `tasks.md`, `design.md` PD-1 to PD-5,
`inputs/qa.md`.

## Prompt
Act as the team lead. Resume openspec/changes/test-memory-followups on branch
docs/plan-test-memory-followups from handover.md: ask me Q1 to Q5, open the plan PR, then deliver
stage 1.
