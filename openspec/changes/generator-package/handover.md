# Hand-over: generator-package, after stage 3

## Done
Stage 1, PR #162; stage 2, PR #166 (merged). Stage 3 (task 3.1, F-4), PR into `develop` (merged
by the watch-and-merge command after this note): the metamodel's schemas say their packages
(`python_package`, `public_package`); the two hard-check rules.

## Decided since the PLAN
D-1 to D-25 (design.md, Delivery decisions). Stage 3: D-21 to D-25.

## Open
- #164 (under-floor hardening, items 1–7), #165 (shims out in 0.6.0).
- `evidence/docs-owed.md` for the docs stage; the scenario-map rows of the new tests (D-17).
- Stage 4's tasks 4.1–4.3 are already built and committed in their worktrees (D-21):
  `.worktrees/gp-s4-4.1` 489051c, `gp-s4-4.2` 9c9cf42, `gp-s4-4.3` 30e4f41. Their deviations to
  record on stage 4's branch: TC-44 is refused by lint, not the hard check (4.1); `closed` cases
  are refused before SHACL, so their report is not asserted (4.2); PD-13's `--python-out` is not
  needed (4.3).
- PR #161 (the developer's) still open (D-7).

## Next
Stage 4: branch from `develop`, cherry-pick 4.1–4.3, task 4.4 (lane, CI Node, docs), then the
full review (D-3) and the reconciliation of `proposal.md` (P-0004). Read first: tasks.md §Stage 4,
design.md PD-11 to PD-13, DEC-9, D-3, D-21.

## Prompt
Act as the team lead. Deliver stage 4 of openspec/changes/generator-package from handover.md,
in .worktrees/lead.
