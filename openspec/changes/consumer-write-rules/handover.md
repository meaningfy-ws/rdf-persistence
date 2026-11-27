# Hand-over: consumer-write-rules, after stage 1

## Done
Stage 1 (tasks 1.1, 1.2, 1.3, 1.5, 1.6; 1.4 stopped), PR #434, merged by the watch-and-merge
command after this note.

## Decided since the PLAN
D-1 to D-14 (design.md, Delivery decisions). The developer decided D-5 (task 1.4 stopped), D-6 (a
living scenario re-signed as MODIFIED) and D-13 (the whole epic in this session); the lead
decided the rest.

## Open
- **Task 1.4, the OpenAPI document (D-5).** Back to a shaping session: `route_options` rated
  CRITICAL on a fresh index. Until it ships, RISK-3 is open: a registered refusal is answered with
  fields that `Problem`'s closed component in the published document does not list. Its signed
  scenario "the document lists the problem" is dropped from this change's delta at the close
  (D-14 C-1). Stage 2 does not depend on it.
- **Under the floor, follow-up candidates:** T-F1 (`refusal_problems` given as a generator) and
  T-F2 (status `409.0`), both D-10; R-S4 (`service.py` docstring, D-12).
- **Carried into stage 2:** the how-to's cold-reader gap, which target generates the problem module
  and where its class is imported from (D-14 C-2), goes to task 2.5.
- **`RuleRefusal` rated CRITICAL by GitNexus** (D-11): an artefact of file-level edges on
  `exceptions.py`.
- **Flaky tooling test** `test_lanes.py::test_on_ci_pytest_runs_unqueued_with_the_workers_counted_by_make`
  (D-7), filed as #432 by `typescript-toolkit-modules`.
- **Environments:** this worktree's `.venv` lacked the extras (`linkml`, `pydantic-settings`) at
  session start; `make install` fixed it. A new worktree needs `make install` before its first seed.
- **The full review** (L1, L2, L3 apart, L4+L5 as one; P-0005) runs once, at the end of stage 2,
  over both stages.

## Next
Stage 2, in this session (D-13), in waves: 2.1 ∥ 2.2 in two worktrees off `develop` after #434
merges; the tester right after 2.1 ∥ 2.3; 2.4 ∥ 2.5; then the full review, the fix pass, the
checker, the acceptance demo offer, the reconcile (P-0004) and the archive. Read first: tasks.md
§2, design.md PD-10 to PD-15 and D-13, D-14, specs/rp-service-api, specs/rp-testkit,
features/consumer_write_rules.feature. Stage start: `make install` in each new worktree,
`make reindex`, impact per task, `make test-seed`.

## Prompt
Act as the team lead. Deliver stage 2 of openspec/changes/consumer-write-rules from handover.md,
following meaningfy-building:epic-delivery and develop/agents.adoc, in parallel waves where the
files allow (D-13); end with the full review (P-0005), the reconcile (P-0004) and the archive.
