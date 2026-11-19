# Hand-over: thematic-structure, after stage 7

## Done
Stage 1 #171, stage 2 #174, stage 3 #175, stage 4 #176, stage 5 #177, stage 6 #178 (merged).
Stage 7 (tasks 7.1, 7.2), PR into `develop` (merged by the watch-and-merge command after this
note): `api` moved, the old layers ended, `.importlinter` in PD-6's final form (17 contracts),
the docs and the CHANGELOG (Changed, Deprecated, Removed). The full review over the EPIC and the
tester ran here: one finding re-labelled Critical and fixed, the accepted ones fixed (D-25).
`proposal.md` reconciled (P-0004, "As built").

## Decided since the PLAN
D-1 to D-25 (design.md, Delivery decisions).

## Open
- Under the review floor, for stage 8 or later (D-25): one shared `_lint` helper; the names
  `LAYERS`, `SHIM_FOLDERS`, `_ENTRYPOINTS`, `_SERVICE_MODELS`, `SERVICE_SCHEMA`; the bus contract
  on the whole `api.services` package; PD-4's folder check requiring a theme before the layer.
- RISK-9 (design, Open Questions) is still the developer's.
- Release-please's open PR proposes 0.6.0; the shims' warnings say "the minor release after the
  one that ships the move", and #165 (the generator shims) also targets 0.6.0: check both when
  the release is cut.

## Next
Stage 8 (task 8.1). Precondition (PD-13, RISK-7): a published release containing stage 7. Do
not start it before. Then: cut `change/thematic-structure-s8` from `develop`; delete
`rdf_persistence/domain/` and `rdf_persistence/adapters/` (the shims), `mint_aggregate_iri`,
`domain-pure`'s and `runtime-without-extras`' shim sources, `rdf_persistence.adapters` in
`domain-tests-stay-in-the-domain`'s forbidden list, `tests/changed.py`'s shim rule
(`SHIM_TESTS`), `SHIM_FOLDERS` and `SHIMS` in the tests and the shims' tests; the public
surface becomes 148 names; CHANGELOG "Removed" (BREAKING). Then the checker, the gates, PR 8,
and archive the change with the scenario map current (`make refresh-map` exits 0).

## Prompt
Act as the team lead. After the release containing stage 7 is published, deliver stage 8 of
openspec/changes/thematic-structure from handover.md, in .worktrees/lead.
