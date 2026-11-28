# Acceptance: aggregate-composition

**Verdict: accepted by the developer, 2026-11-28** ("I accept and do ea probe to complete epic").

The developer accepted the delivered change as a whole: the scenarios, the DEC-4 re-shape and the
DEC-2 amendment, the delivery decisions D-1 to D-17, and the rules P-0025 to P-0040. At the
developer's request the lead ran the EA probe (task 1.13) on the EA-saved models available; it is
recorded in `ea-connectors.md`, and RISK-9 is closed with one accepted residual (no composite
`Aggregation` was found to read). No demo was run: the developer accepted on the delivered evidence.

The record below is kept as written while the acceptance was pending.

---

2026-11-28, pending: **deferred to the developer**, who was away and had granted delivery to the
end.

## What the developer validates

1. The scenarios (`features/*.feature`), accepted by the lead under the grant
   (`scenario-signoff.md`).
2. The EPIC changes made by the lead: DEC-4 re-shaped (a tree of instances) and DEC-2 amended (a
   role on the composition picks among candidate associations), both in `inputs/qa.md`.
3. The delivery decisions D-1 to D-16 in `design.md`.
4. The adopted modelling rules P-0025 to P-0040 in `docs/rules/` (the script stamps `approved`; the
   developer's approval is the merge of this change and this validation).
5. RISK-9, the `@manual` scenario "An EA-drawn composition reads the same either way": draw, in a
   scratch `.qea` saved by EA, one composition whole → part, one part → whole and one shared
   aggregation; `rp-uml2linkml --check` and a conversion must read both compositions the same way
   and refuse the shared one. Record the columns in `ea-connectors.md`.

## Notes for the validation (end-of-epic review, D-17)

- The scenario "a generated part in its own graph" of `own_graph_and_pointers.feature` was replaced
  by the change `dependent-aggregates` (its generation scenario 12): it is accepted there.
- `composition-named` and `implicit-meaning` fail `--check` (they are in `CONVENTION_KINDS`) but
  have no spec scenario of their own; unit rows prove them (`test_uml_conventions.py`,
  `test_uml_aggregates.py`).
- Task 1.13 (the EA probe) stays open until the developer runs it.

## The demo to run (suggested)

On a copy of a consumer model: draw one Aggregation beside an association, drop «root» from a
class, run `rp-uml2linkml --check` (exit 1 names any composite association; after the redraw, exit
0 with `root` lines), convert, and diff the schemas against the previous release's output per the
guide's "Redrawing a boundary model".
