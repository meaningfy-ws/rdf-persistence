# Hand-over: activity-iri-policy, stage 1 delivered (2026-11-25)

## Done
Stage 1, the only stage, is built and gated in PR #407 (`feat/activity-iri-policy` into
`develop`). Tasks 1.1 to 1.9 are ticked. The developer granted commit, push and merge on green CI
for this epic, and skipped the acceptance demo (`evidence/acceptance.md`).

- 1.7: the three signed-off scenarios are appended verbatim to `tests/feature/iri_policy.feature`
  with their steps; no production code changed.
- 1.6: re-proved by the seed on the rebased branch (every unit and feature test once, green).
- 1.7a: IT-A1 to IT-A3 pass on Fuseki in `make test-containers`.
- 1.9: `make check-all` twice (before and after the fix pass), `make test-containers` once,
  `make check-generated` twice, all green; results in the PR body and `evidence/acceptance.md`.
  One L2+L3 review pass: 0 Critical; R-W1 to R-W3 fixed (30ec5ddd); the rest under the floor
  (design.md D-5).

## Decided since the PLAN
D-1 to D-5 (design.md, Delivery decisions). D-4 retires D-1: with the test queue the runs finish.

## Open
- Under the floor (D-5), candidates for a later review-floors change: the dead `getattr` in the
  feature test's `Run`; `_WORD` duplicated in `iris/domain/layout.py` and
  `tenancy/services/tenant_move.py`; the "provisional or placed" check in three places; no test of
  an activity committed through an application-scoped session; `is_aggregate_graph`'s
  `is_activity` check that never matches a graph IRI.
- Stage start: `make reindex` was skipped because another session was indexing; no impact run
  was needed for task 1.7 (tests only).
- Merge order: consumer-friction (#391) merged first, by the developer's order with `--admin`
  while its "Generator tests" job was still running; #407 was rebased on it (its new TypeScript
  modules regenerated with `activity_template`, 8d629101) and gated again with `make check-all`.
  The developer ordered #407 merged with `--admin` on a passing local `make check-all` (P-0021).
  **#407 is not merged yet**: the session closed while that `make check-all` on 8d629101 was
  running (log `temp/check-all-3.log` in the worktree, if it finished). Watch develop's CI for
  #391's generator job.
- The consumer (MWBv2) names toolkit change `activity-iri-policy` in its URI-policy change (D-12);
  the PR body says so.

## Next
1. Read `temp/check-all-3.log` in the worktree. If it ends in "Full verification suite passed"
   and the branch head is still this note's commit with develop unmoved, that is the gate;
   otherwise fetch, rebase on develop (P-0003 for generated files) and run `make check-all` once
   (no seed: no builders follow, P-0022).
2. Paste the result into #407's body (Results), then `gh pr merge 407 --merge --admin`
   (developer's order, 2026-11-25).
3. Archive the change (`spec-stewardship`, `openspec archive activity-iri-policy --yes`) in its
   own PR, update `openspec/changes/README.md` (row 60), remove `.worktrees/activity-iri-policy`.
   When a release ships, comment it on #197.

## Prompt
Act as the team lead (epic-delivery). Finish openspec/changes/activity-iri-policy from its
handover.md in .worktrees/activity-iri-policy: confirm the last local make check-all on PR #407,
merge #407 with --admin, archive the change, update openspec/changes/README.md, remove the
worktree, and comment the release on #197 when it ships.
