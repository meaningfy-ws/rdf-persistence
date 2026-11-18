# Hand-over: thematic-structure, after stage 4

## Done
Stage 1 #171, stage 2 #174, stage 3 #175 (merged). Stage 4 (tasks 4.1, 4.2), PR into `develop`
(merged by the watch-and-merge command after this note): `SparqlProtocolStore` and `FusekiStore`;
`persistence` and `migrations` moved; the `adapters.fuseki` shim; persistence and migrations
served from their own schemas; a component two served schemas declare is an error (D-19).
Checker: pass.

## Decided since the PLAN
D-1 to D-19 (design.md, Delivery decisions).

## Open
- Stage 7 removes the temporary contracts (`themes-never-import-the-old-layout`, the four
  `old-vs-themes`), and its CHANGELOG names the moved logger names, `error.type`, the 400 log
  line and the IRI wrappers (D-12 (7), D-15 (8), D-18 (5)).
- `evidence/docs-owed.md` for task 7.2.

## Next
Stage 5 is built in `.worktrees/ts-s5` (63299b5 move, a13343c TypeScript golden in served order,
proven order-only); stage 6 in `.worktrees/ts-s6` (1ea2a06, 161d2ec); task 7.1 in `.worktrees/ts-s7`
(d9b7679). Cut `change/thematic-structure-s5` from `develop` after this merge, cherry-pick stage
5's two commits, settle conflicts (docs by combining; `.test_durations` and the scenario map by
regenerating and re-mapping), record its D-n from the lead's `temp/session-state.md`. Detach
`.worktrees/lead` from the PR branch before every watch-and-merge (D-18 (13)). Re-index after
each merge.

## Prompt
Act as the team lead. Deliver stage 5 of openspec/changes/thematic-structure from handover.md,
in .worktrees/lead.
