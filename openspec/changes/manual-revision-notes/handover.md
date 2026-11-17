# Hand-over: manual-revision-notes, after stage 3

## Done
Stage 3 (representations, contract, decisions; tasks 3.1–3.4 and the reconciliation), PR #151
(merged by the watch-and-merge command after this note). This was the last build stage. The
developer skipped the acceptance demo (`evidence/acceptance.md`); no docs stage is owed
(`evidence/docs-owed.md`).

## Decided since the PLAN
PD-17; D-1 to D-20; F-1 to F-12 and the floor lists of stages 1, 2 and the full review (design.md,
Delivery decisions).

## Open
- #148: the generated component schemas omit `type`; five operations' schema checks are
  `xfail(strict=True)` in `tests/unit/entrypoints/test_contract.py`.
- #153: the events route documents each SSE event as a string; one strict xfail.
- #142 stays quarantined; the pyoxigraph follow-up needs the developer (PD-17).
- An intermittent pyparsing error (`Param.postParse2()`) under concurrent runs (D-19).
- The full review's floor list (design.md), first L4+L5 W3 (the RDF serialisations run on the
  event loop) and L1 S1 (a JWK with `use: enc` is kept).

## Next
Archive the change (`spec-stewardship`). In the same PR, bring `tests/audit/scenario-map.csv` up to
date: the 38 rows that name the renamed requirement (D-16) and a row for every test this EPIC added
(D-18; `make refresh-map` exits 0). Read first: design.md D-16, D-18, the spec deltas.

## Prompt
Act as the team lead (epic-delivery). Archive openspec/changes/manual-revision-notes from
handover.md: one PR into develop from branch change/manual-revision-notes-archive.
