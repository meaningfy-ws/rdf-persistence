# Hand-over: manual-revision-notes, after stage 2

## Done
Stage 2 (reuse, tasks 2.1–2.5), PR #143 (merged by the watch-and-merge command after this note).
Task 2.5 kept `FakeStore` on rdflib (PD-17); the pyoxigraph attempt is in
`evidence/spike-pyoxigraph-fakestore.patch`.

## Decided since the PLAN
PD-17; D-8 to D-13; F-3 to F-6 and the stage 2 findings under the floor (design.md, Delivery
decisions). The developer granted the lead the merge on green CI until this EPIC ends (D-13).

## Open
- The full review (L1, L2, L3, L4+L5) runs once after stage 3 (D-1, P-0005); it weighs both
  stages' findings under the floor, first `RpModel.replaced` (stage 1 L3 W1) and the broad
  `except Exception` around `triples_of` (stage 2 L3 W2).
- A follow-up for pyoxigraph (`make test-fast` about twice as fast, #142's test 0.3 s) needs the
  developer: the three engine-bound test edits and oxigraph's `NOT IN ()` defect (contribute
  upstream, or work around it in the fake) (PD-17). #142 stays quarantined.
- Task 3.3 edits `howto/adopt.adoc`: the cold reader's older gaps in its load section are listed
  under the floor.
- Builders in worktrees: Serena's project is the main checkout, so they edit with Edit only; uv
  needs the sandbox disabled; a fresh worktree needs `make install`. A new `RpAnnotation` member
  needs a group in `generation/checks/hard.py`, and editing `hard.py` needs `make generate`.

## Next
Stage 3, task 3.1. Read first: tasks.md §Stage 3, design.md PD-12, PD-14, PD-15, PD-16, D-13 and
the stage 2 findings, `specs/rp-service-api/spec.md`.

## Prompt
Act as the team lead (epic-delivery). Deliver stage 3 of openspec/changes/manual-revision-notes
from handover.md: one PR into develop from branch change/manual-revision-notes-s3.
