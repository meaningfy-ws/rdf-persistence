# Hand-over: otel-observability, after stage 2

## Done
Stage 2 (spans, the broker seam, BDD and the how-to, tasks 2.1–2.6) and the epic's full review
with its fix pass, PR #152 (merged by the watch-and-merge command after this note). Stage 1 was
PR #149. All build tasks are ticked; `proposal.md` carries the "As built" reconciliation.

## Decided since the PLAN
D-1 to D-13 (design.md, Delivery decisions), and the floor lists of stages 1 and 2. D-10 and D-11
are the full review's accepted Critical findings (no exception text in a span; no traceback in the
500 record where stored values could be quoted).

## Open
- **For the developer:** L4/L5-W4, whether expected refusals (`Conflict`, `NotFound`,
  `BadQuery`) should mark spans ERROR (today they do; TC-31 asserts it). A spec decision, listed
  under the stage 2 floor.
- **Acceptance demo:** offered, not run; the developer asked for no questions in this session
  (`evidence/acceptance.md`). Validation stays with the developer.
- **Docs stage (D-13):** `rp.sweep.system_created`'s description in the how-to and the schema;
  `event-driven.adoc` omits `middlewares=`; the how-to's store-span table omits `rp.step`.
- **Consumers (D-12 of AGENTS.md):** BREAKING for log readers (DEC-10) and for a consumer schema
  with a non-identifier alias (D-4); MWBv2's change should name this one.

## Next
After the merge: the acceptance record, the docs stage (D-13), then archive with `openspec archive
otel-observability --yes` per `spec-stewardship`.

## Prompt
Act as the team lead (epic-delivery); read docs/modules/ROOT/pages/develop/agents.adoc. Close
openspec/changes/otel-observability from handover.md: the acceptance demo with the developer, the
docs stage of D-13 in one PR, then archive the change.
