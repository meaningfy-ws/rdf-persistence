# Hand-over: uml-roles-and-workflows, after stage 2

## Done
Stage 1 (role definitions, 1.1–1.4) and stage 2 (workflows, 2.1–2.4) with the EPIC's full review,
its fix pass and the checker; accepted to merge on fixtures (evidence/acceptance.md); no further
docs owed (evidence/docs-owed.md). Stage 2's PR is merged by the watch-and-merge command after this
note.

## Decided since the PLAN
D-1 to D-16 (design.md, Delivery decisions).

## Open
- D-8, D-12b: the real-model run. The first consumer fixes the boundary with no root in its access
  package; then rerun `rp-uml2linkml` on its model with roles and workflows in one run (RISK-3)
  and fill `evidence/real-model-run.md` (files written, report lines, loaders).
- Follow-up issues (D-16): #258 the roles file's encoding in the library; #259 the library's
  whole-model workflow check in `write`; #260 a nesting role fixes `member_class`; #261 the
  service-start docs.
- D-11: the review's findings under the floor, follow-up candidates.

## Next
Archive the change per spec-stewardship: sync `specs/rp-uml-import/spec.md` into
`openspec/specs/rp-uml-import/`, `openspec validate --all --strict`, move the change to
`openspec/changes/archive/`, in its own PR. Read first: this note, design.md D-12, tasks.md §3.

## Prompt
Act as the team lead. Archive openspec/changes/uml-roles-and-workflows from handover.md.
