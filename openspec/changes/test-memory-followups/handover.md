# Hand-over: test-memory-followups

## Done
- 2026-11-25: EPIC shaped (SMALL, DEC-1 to DEC-4), PLAN gated 8.9 (accepted, R-0005); DEC-5 and
  DEC-6 added after the gate; parked.
- 2026-11-26: resumed after `test-control-testkit` (archived). Rebased on `develop`. The developer
  answered Q1 to Q5 as recommended and folded in #416's fallback gap: DEC-7 / PD-8, task section 4,
  the `rp-testkit` delta, appetite MEDIUM (`inputs/qa.md` round 3). PD-6 reworked to the
  current seed (`selection_data seed`) and the real lane commands; the `rp-developer-checks` delta
  drafted, conditional on the spike. Gaps-only gate over the additions: see
  `evidence/clarity-gate.md`.

## Next
Open and merge the plan PR, then deliver the one stage: `make reindex`, `make test-seed` in the
background, builders on 1.1, 1.2, 1.3, 4.1 in parallel, the lead on the spike 2.1; then 4.2, 2.2,
4.3; the close 3.1 (MEDIUM in one stage: L2+L3 and the full review on the same PR). 3.2 (DEC-8)
needs epic sessions on `develop` after #394; 3.3 archives.

## Prompt
Act as the team lead. Resume openspec/changes/test-memory-followups on branch
docs/plan-test-memory-followups from handover.md: open the plan PR, then deliver the stage.
