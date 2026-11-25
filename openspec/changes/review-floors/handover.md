# Hand-over: review-floors, all three stages merged (2026-11-25)

## Done
- Plan PR #384 merged (EPIC, PLAN gated 9.4, scenarios signed off).
- Stage 1 merged as #393, stage 2 as #400, stage 3 as #401 (the PR this note closes).
- Both branches were rebased onto 0.15.0 (the test-control system) and onto #398/#399 with no
  conflict (D-12).
- Full test run on the stage 3 tip, which carries all three stages:
  - `make check-quality`;
  - unit and feature tests from the seed (10251 passed, D-13);
  - `make test-generator` (1789 passed, 96.96 %);
  - `make test-containers` (368 passed, the e2e tests included, D-14);
  - `make check-generated`;
  - `make refresh-map` (only other changes' tests unmapped).
  The stage 2 tip ran `make check-quality` and `make test-generator`. Results are in #400 and #401.
- D-9 settled by the owner: the tripwire became a pass-through spy, so `# X2` fits rule 3.
- Stage 2 merged ahead of #391 and activity-iri-policy, by the owner's decision.

## Decided since the PLAN
D-1 to D-14 (`design.md`, Delivery decisions). New in this session:
- D-12: the rebase onto 0.15.0;
- D-13: the seed stands for the unit and feature tiers;
- D-14: the s3 run covers s2, with no separate e2e run;
- D-9: settled as a spy.

## Open
- GitNexus was not re-indexed in this session: another session held the index (D-1, D-12).

## Next
1. Task 4.1: post `close-comments.md` (PRLIST = #393, #400, #401; PRS1 = #393; NEWISSUE = the
   189-v issue, opened first); close #215, #272, #273 and #275; narrow the rest. Link the full
   test result from #393.
2. Task 4.2: archive per `spec-stewardship`; update `openspec/changes/README.md`.
3. Remove `.worktrees/review-floors-s2` and `.worktrees/review-floors-s3`.

## Prompt
Act as the team lead. Close openspec/changes/review-floors from handover.md: post the issue
comments (task 4.1), archive the change (task 4.2), update openspec/changes/README.md and remove
its worktrees.
