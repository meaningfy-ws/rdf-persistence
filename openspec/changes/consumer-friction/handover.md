# Hand-over: consumer-friction, after stage 1

## Done
Stage 1 (the only stage), PR #391, rebased on `develop` after 0.15.0 and review-floors, merged by
the watch-and-merge command after this note. #371 and #372 close with the merge.

## Decided since the PLAN
D-1 to D-9 (design.md, Delivery decisions). D-8: the review of the rebased head, no Critical.
D-9 (corrects D-7): the generator lane's CI failures came from this change, since every TypeScript
target rebuilt the served types; they are built once per process now.

## Gates
- `make check-all` before the PR: passed (unit 8427, feature 99, generator 1788).
- `make check-all` after the fix pass (D-9): passed (unit 8427, feature 99, generator 1789 in 93 s).
- After the last rebase (manifests regenerated only): `make check-quality` passed; CI decides.
- One toy generation: 6.45 s, develop 5.39 s (20.9 s vs 14.2 s profiled before the fix).
- `make reindex` stopped at its 10-minute limit at stage start; the stage used the existing index.

## Open
- Under the floor, worth one follow-up test each: L2-1 (`_typescript_owners` with an owner target
  that sets no `typescript`) and L2-2 (an owner outside the project). The rest: D-5, D-6, D-8.
- The lane's headroom: `test_lock_step` regenerates the whole toy per test; if a slow runner times
  it out again, give those tests a toy without TypeScript targets.
- Consumer: MWB2 `v2-05` regenerates and moves its imports (RISK-1).
- On release: comment the version on #371 and #372.

## Next
Archive per `spec-stewardship` in its own PR off `develop`: `openspec archive consumer-friction
--yes` (syncs the requirement into `openspec/specs/rp-generation/spec.md`), update
`openspec/changes/README.md`. Acceptance: skipped by the developer, accepted
(`evidence/acceptance.md`).
