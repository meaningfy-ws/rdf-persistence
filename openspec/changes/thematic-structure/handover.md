# Hand-over: thematic-structure, after stage 5

## Done
Stage 1 #171, stage 2 #174, stage 3 #175, stage 4 #176 (merged). Stage 5 (task 5.1), PR into
`develop` (merged by the watch-and-merge command after this note): `access` and `tenancy` moved,
with `tenant_move`; the wire schema split into `rp_access_adapters`; access and tenancy served
from their own schemas; `tenancy-without-the-runner` retargeted. Review: no Critical; the
accepted findings fixed (D-21). Checker: pass.

## Decided since the PLAN
D-1 to D-21 (design.md, Delivery decisions).

## Open
- Stage 7 removes the temporary contracts (`themes-never-import-the-old-layout`, the four
  `old-vs-themes`) and the two planting tests in TC-04's `EXEMPT`, and its CHANGELOG names the
  moved logger names, `error.type`, the 400 log line and the IRI wrappers (D-12 (7), D-15 (8),
  D-18 (5)).
- `evidence/docs-owed.md` for task 7.2.

## Next
Stage 6 is combined in `.worktrees/ts-s6-comb` (`change/thematic-structure-s6`, D-22) and its
review fix (D-23) is built in `.worktrees/ts-s6-tester`; rebase it onto this merge, run the
gates, check, merge. Task 7.1 is combined onto stage 6 in `.worktrees/ts-s7-comb`
(`change/thematic-structure-s7`, 98b04e3): rebase after stage 6, retarget the D-23 bus contract
to `api.services`, map its 15 unmapped tests. Detach `.worktrees/lead` from the PR branch before
every watch-and-merge (D-18 (13)). Re-index after each merge.

## Prompt
Act as the team lead. Deliver stage 6 of openspec/changes/thematic-structure from handover.md,
in .worktrees/lead.
