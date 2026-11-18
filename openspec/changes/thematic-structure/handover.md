# Hand-over: thematic-structure, after stage 3

## Done
Stage 1 #171, stage 2 #174 (merged). Stage 3 (tasks 3.1, 3.2), PR into `develop` (merged by the
watch-and-merge command after this note): `iris` (the 11 IRI wrappers removed,
`mint_aggregate_iri` warns), `schema` (with the six term bundles), `files`, `provenance`; the
contracts and the model guard derive their themes from `TURNED_ON` (D-16).

## Decided since the PLAN
D-1 to D-17 (design.md, Delivery decisions).

## Open
- Stage 7 removes the temporary contracts `themes-never-import-the-old-layout` and the four
  `old-vs-themes` contracts with the old layout; its CHANGELOG lists the moved logger names
  (D-12 (7), D-15 (8)).
- `evidence/docs-owed.md` for task 7.2.

## Next
Stage 4 is built in `.worktrees/ts-s4` (a069a31 move, 3de626d `adapters.fuseki` shim, d060813
the served TypeScript golden in served-schema order, proven order-only) on 330e041; cut
`change/thematic-structure-s4` from `develop`, cherry-pick the three, settle conflicts (docs by
combining both sides, `.test_durations` by regenerating), record D-18 (the lead's
`temp/session-state.md` lists its items) and add the test tying `themes-layered`/`themes-ordered`
to `TURNED_ON` (D-17 W2). Stage 5 is building in `.worktrees/ts-s5` on d060813. Re-index Serena
and GitNexus after this merge.

## Prompt
Act as the team lead. Deliver stage 4 of openspec/changes/thematic-structure from handover.md,
in .worktrees/lead.
