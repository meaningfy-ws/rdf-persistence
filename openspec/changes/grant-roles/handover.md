# Hand-over: grant-roles, after stage 1

## Done
Stage 1 (#307: grants in a migration, the start-up report), PR #345 (merged by the watch-and-merge
command after this note). #307 is answered on the issue with a link to `howto/migrate.adoc#roles`.

## Decided since the PLAN
D-8, D-9, D-10, D-11 (design.md, Delivery decisions).

## Open
- D-8 (`migration_request` HIGH impact, taken by the lead) and the two re-labelled findings of D-11
  wait for the developer's validation at the end (R-0007).
- Under the floor (D-11): R1-W3, R1-S4, R1-S5.
- `aggregate-guards` (row 15) merged (#346) and was archived (#348) while stage 1 was in review;
  stage 1 was rebased over it. Stage 2 touches `collaboration.py`, the router and `openapi.py`,
  which it changed: read their current state, not the line numbers in design.md.
- The GitNexus re-index failed once before the stage's last commit; the agents.adoc recovery
  (`gitnexus clean --force`, then a forced `analyze`) restored it. Its `detect_changes` against
  `develop` read "critical" but counted develop's newer generator files as the stage's (the index
  predates the aggregate-guards merge); the stage's own sources are the five files of D-1 to D-5,
  whose one HIGH impact is D-8. Re-index at stage 2 start.

## Next
Stage 2 (#310), task 2.1, branch `feat/held-roles`. Read first: tasks.md §2, design.md D-6, D-7,
the stage 2 T-table (T10–T13) and E10–E12, `specs/rp-access/spec.md` (roles held).

## Prompt
Act as the team lead. Deliver stage 2 of openspec/changes/grant-roles from handover.md, then close
with tasks 3.1 and 3.2.
