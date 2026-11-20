<!-- Secondary input, never groomed. The owner's answers to the PLAN's open questions, relayed by the coordinator. -->

# Owner answers 2026-11-20

| Question | Planner's recommendation | Owner's answer | Becomes |
|---|---|---|---|
| OPEN-1 Empty text (`label~=`) | 400 `bad-query` | Accepted | PD-10 |
| OPEN-2 `Contains` hand-written or generated | hand-written frozen dataclass | **Against the recommendation:** generated from LinkML; AGENTS.md principle 2 applies | PD-7 (class in `rp_persistence_services.yaml`, `make generate`; built as `Contains(text=…)`) |
| OPEN-3 `rp-aggregate-store` delta | add it | Accepted | PD-11, `specs/rp-aggregate-store/spec.md` |

Reviewer's gate (8.8/10), accepted under the owner's rule R-0005; its gaps were folded without a
re-run: DEC-1 read as "escaped literal through `term()`" (PD-5) with an injection row (TC-04,
TC-06); scenarios aligned with the toy `Book` and mapped to TCs (PD-12); scenarios added for the
OpenAPI `~` parameters, the empty text and an item matching on several values; line references
corrected (`schema_structure.py:127`, `reference_collections.py:101`).
