# Hand-over: activity-iri-policy, stage 1 parked mid-build (2026-11-25)

## Done
Stage 1 is parked before its PR; no PR is open. Branch `feat/activity-iri-policy` (pushed) holds
tasks 1.1 to 1.5, 1.6 (all four tests), 1.7a and 1.8, one commit each. Task 1.7 is not started.
The developer granted commit, push and merge on green CI for this epic.

What is proven and what is not, per task (the commit bodies say the same):
- 1.2, 1.3: narrow test folders and `check-quality` green; full `test-fast` never finished (D-1).
- 1.4: tenancy, persistence, provenance, messaging, events green; `tests/unit/api` and
  `tests/unit/collaboration` never finished a run.
- 1.5: events, the route test and the session tests green (146 passed) with 1.4 in place.
- 1.6: the three guard and dump-check tests and `check-quality` green; the restore test passed
  alone and fails under a mutation, its gate never ran.
- 1.7a: written, collects (3 tests); never run on Fuseki.
- 1.8: `check-docs`, `lint`, `check-quality` green; no tests run.

## Decided since the PLAN
D-1, D-2, D-3 (design.md, Delivery decisions).

## Open
- Pytest runs on the shared machine were killed from outside (SIGTERM, exit 143) many times; one
  cause was another session's `pkill -f pytest`. The developer stopped all tests and is changing
  the testing setup on `develop`. D-1 is a workaround for that; drop it if the new setup makes
  `make test-changed` / `make check-all` finish.
- `make reindex` hung for 30 minutes at stage start and was stopped; impact was read from the
  stale index (all LOW).
- The branch is behind `develop`: rebase it first (P-0002). Generated files may conflict: per
  P-0003 take develop's generated file, carry the source change, run `make generate`.

## Next
Stage 1, task 1.7, then 1.9. Read first: `tasks.md` 1.7 and 1.9, `features/iri_policy.feature`
(signed off: copy verbatim), `design.md` D-1 to D-3. Then the full gates once (`make check-all`,
`make test-containers` for 1.7a, `make check-generated`), one L2+L3 review pass (SMALL, P-0005),
the PR, `evidence/acceptance.md`, this note re-written last, watch-and-merge, archive.

## Prompt
Act as the team lead (epic-delivery). Resume stage 1 of openspec/changes/activity-iri-policy from
handover.md: rebase feat/activity-iri-policy on develop in .worktrees/activity-iri-policy, build
task 1.7, then run task 1.9 (full gates, review, PR, merge). The commit/push/merge grant for this
epic stands.
