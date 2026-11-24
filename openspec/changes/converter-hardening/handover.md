# Hand-over: converter-hardening, after stage 1

## Done
Stage 1 (the only stage), PR #349 (merged by the watch-and-merge command after this note).

## Decided since the PLAN
OPEN-6 (inputs/qa.md, PD-5); D-1, D-2, D-3, F-T1, F-T2, R-W1 to R-S6 (design.md, Delivery
decisions).

## Open
- RISK-4 for generator-module-cycles (#208/#206): when the converter writes modules that import
  each other, re-run `test_the_start_up_check_refuses_a_staged_workflow` on a cyclic pair; the
  whole-model check loads the staged schema with `SchemaView`.
- #343 the deferred restructure of #229 (DEC-1); #344 a tutorial from a UML model to a toy
  service (D-3).
- Session note: the builders' task gate (`make test-changed check-quality`) never finished under
  the load of parallel sessions; `test-changed` widens to the fast suite whenever a converter edit
  regenerates the manifests (D-1).

## Next
Close the EPIC: the acceptance demo offer (`evidence/acceptance.md`), `evidence/docs-owed.md`,
then archive (`openspec archive converter-hardening --yes`).

## Prompt
Act as the team lead. Close openspec/changes/converter-hardening from handover.md: offer the
acceptance demo, record docs owed, archive.
