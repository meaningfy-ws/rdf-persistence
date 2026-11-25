# Hand-over: consumer-friction, after stage 1

## Done
Stage 1 (the only stage), PR #391 (merged by the watch-and-merge command after this note).

## Decided since the PLAN
D-1 to D-5 (design.md, Delivery decisions).

## Open
- Review findings (one pass, L2+L3): C1 accepted and fixed (D-5, commit "take TypeScript owners
  from the run's targets"); W1's third case, W2, S1, S2 under the floor (D-5).
- A second session ("Plan consumer-friction fixes for #371 and #372") ran this EPIC's delivery
  after a restart and edited this worktree during the fix pass; its edits matched D-5 and were
  reviewed before the commit, and it stepped back (D-6 records its review). Its post-fix
  `make test-generator`: 1781 passed, 7 failed, all in `test_freshness.py` on pytest-timeout
  (>120 s) under three sessions' suites; the file passes alone (30 passed).
- **Incident:** a fixer of that session ran `pkill -f pytest` around 18:00, which may have killed
  pytest runs of other sessions (`review-floors-s1`, `activity-iri-policy`); those sessions should
  re-run any gate that ended then. Session hygiene: two sessions on one change's worktree race each
  other, and processes are never killed by pattern.
- CI: every lane green on the rebased head (unit 1/8–8/8, coverage floor, feature, types with
  `make typecheck-ts`, style, architecture, spec/docs/generated code, docs build), except the
  generator lane: on the first push GitHub's runner shut down mid-job, on the second it stopped at
  its 30-minute limit with no log kept (on `develop` it takes 11–17 min). `test_freshness.py`
  takes 98 s on `develop`'s base and 103 s here, so the change does not slow it; the merge waits
  for the generator lane on the commit that carries this note. The local unit lane did not finish
  (D-4), so CI is the test evidence.
- Acceptance demo: offered (SMALL, may be skipped); verdict or skip goes to `evidence/acceptance.md`.
- Docs: none further owed (`evidence/docs-owed.md`).
- #371 and #372 close with the merge.
- Consumer: MWB2 `v2-05` regenerates and moves its imports (RISK-1).

## Parked (2026-11-25, evening)
PR #391 is **not merged**. Every CI lane is green except "Generator tests", which failed three
runs in a row: the pytest process is killed (SIGTERM, once "runner received a shutdown signal")
about 20 minutes in; progress is normal to 76 %, then 4–5 min per 4 %. On `develop` the lane takes
11–17 min. Hypothesis, not proven: memory exhaustion on the 4-core/16 GB runner from something this
branch adds (three TypeScript targets in the toy, each building the served-type generators; or
`run_toy` reading the toy's targets on every call). `test_freshness.py` alone is unchanged
(98 s vs 103 s). The diagnosis was stopped by the developer before it reported.
`develop` has moved since (review-floors stage 1, #393, changes to the testing system): rebase
first, then diagnose.

## Next
Close: offer the acceptance demo, record the verdict, then archive per `spec-stewardship`
(`openspec archive consumer-friction --yes`; syncs the new requirement into
`openspec/specs/rp-generation/spec.md`). Read first: tasks.md 1.5, design.md D-4,
proposal.md Reconciliation.

## Prompt
Act as the team lead for consumer-friction, stage 1, PR #391 (branch change/consumer-friction,
worktree .worktrees/consumer-friction). Read handover.md, then design.md D-1 to D-6. Rebase on
develop (P-0002), diagnose why CI's generator lane is killed (compare the lane with -n 4 on develop
and on the branch: wall time, peak RSS, slowest tests), record the fix as D-7, one fixer, the gates,
then merge on green CI (D-1 grant). Then the acceptance demo offer, the archive.
