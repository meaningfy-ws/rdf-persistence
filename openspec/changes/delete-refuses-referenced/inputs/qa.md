<!-- Secondary input, never groomed: the owner's answers to the planner's questions, relayed by
     the coordinator. The EPIC (../proposal.md) and the PLAN (../design.md) supersede it. -->

# Q&A: delete-refuses-referenced

## Round 1, 2026-11-20 (planner's PLAN run 1; owner's answers relayed by the coordinator)

| # | Question | Owner's answer |
|---|---|---|
| 1 | The atomic guard needs a guard in the delete's update request, signature changes and a problem model, more than SMALL allows. Re-shape, or cut scope? | Re-shape upward: SMALL → MEDIUM, keep the atomic guard design. Log it in proposal.md (Appetite, Solution outline). |
| 2 | DEC-2 says a concurrent referrer is "either seen or blocked"; one written after the delete is neither. Narrow DEC-2? | Yes: "no referrer exists at the moment the delete applies; a referrer written after it is not blocked". Amend DEC-2 in the same logged re-shape. RISK-1 accepted. |
| 3 | OPEN-1: a cascade with a refusing member referenced from outside it. | Recommendation accepted: refuse the whole cascade, nothing deleted. |
| 4 | OPEN-2: does a collection's `had_member` link block deleting the member? | Recommendation accepted: yes, it is a referrer like any other. |
| 5 | OPEN-3: the annotation on a `rp_writes: service` class. | Recommendation accepted: allowed; the session honours it, the toolkit adds nothing to the application's routes. |
| 6 | OPEN-4: the spec delta lacks the `rp-service-api` 409 `in-use` requirement and a cascade scenario. | Recommendation accepted: add both now (done: `specs/rp-service-api/spec.md`, two cascade scenarios in `specs/rp-reverse-references/spec.md`). |

## Gate run 1 (fresh reviewer), 2026-11-20: 8.4/10, fail

Gaps 1 to 10 of the first fresh run, grouped here as 7 fixes (E8 citation, TC id for `InUse`, a third integration test, the `InUseProblem` slots in
task 1.1, the annotation's real inheritance rule, the quote's line numbers, comment referrers vs
DEC-3) are fixed in design.md and tasks.md; see `../evidence/clarity-gate.md`.
