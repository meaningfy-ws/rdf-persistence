# Hand-over: thematic-structure, after stage 6

## Done
Stage 1 #171, stage 2 #174, stage 3 #175, stage 4 #176, stage 5 #177 (merged). Stage 6 (task
6.1), PR into `develop` (merged by the watch-and-merge command after this note): `events`,
`collaboration` and `messaging` moved; events and collaboration served from their own schemas;
`nothing-in-services-imports-the-bus` removed, its `api` half kept by
`api-services-never-import-the-bus` (D-23). Review: one finding re-labelled Critical and fixed,
the accepted ones fixed (D-23). Checker: pass; PD-6 and task 7.1 now name the new contract.

## Decided since the PLAN
D-1 to D-23 (design.md, Delivery decisions).

## Open
- Stage 7 removes the temporary contracts and the old layout's planting tests, retargets
  `api-services-never-import-the-bus` to `api.services`, and its CHANGELOG carries
  `evidence/docs-owed.md`'s rows.

## Next
Task 7.1 is combined onto stage 6 in `.worktrees/ts-s7-comb` (`change/thematic-structure-s7`):
rebase after this merge; task 7.2's docs are being written there. Then the full review (L1, L2,
L3 apart, L4+L5), tester, checker, reconcile `proposal.md` (P-0004), gates, PR 7. Stage 8 waits
for a published release containing stage 7. Detach `.worktrees/lead` from the PR branch before
every watch-and-merge (D-18 (13)). Re-index after each merge.

## Prompt
Act as the team lead. Deliver stage 7 of openspec/changes/thematic-structure from handover.md,
in .worktrees/lead.
