# Hand-over: thematic-structure, after stage 2

## Done
Stage 1, PR #171 (merged). Stage 2 (task 2.1, `core`), PR into `develop` (merged by the
watch-and-merge command after this note): the metamodel, base model, exceptions, media, SPARQL and
its parser in `core.domain`; artifacts, YAML files, telemetry in `core.services`; the HTTP helper
in `core.adapters`; `HttpSettings` and `LogContext` in the core services schema; the
`domain.base` shim (warns once); the theme contracts and the temporary contracts that keep the
moved and the unmoved layouts apart until stage 7 (D-13, D-14).

## Decided since the PLAN
D-1 to D-14 (design.md, Delivery decisions).

## Open
- #173 closed by this stage (D-13 W1).
- Stage 7 removes the five temporary contracts (`core-never-imports-the-old-layout` and the four
  `old-*` ones) with the old layout, and its CHANGELOG says `error.type` changed (D-12 (7)).
- `evidence/docs-owed.md` for task 7.2.

## Next
Stage 3: task 3.1 (`iris`) is built in `.worktrees/ts-s3-3.1` (cc1bbbb, on 5e76711, before D-13
and D-14) and task 3.2 is building in `.worktrees/ts-s3-3.2`; cut `change/thematic-structure-s3`
from `develop` after this merge, cherry-pick both, settle conflicts in `.importlinter`,
`test_theme_layout.py`, `test_model_guard.py`, record 3.1's deviations as D-15. Re-index Serena and
GitNexus after this merge. Read first: tasks.md §Stage 3, design.md PD-5, PD-2, PD-10, D-8, D-10.

## Prompt
Act as the team lead. Deliver stage 3 of openspec/changes/thematic-structure from handover.md,
in .worktrees/lead.
