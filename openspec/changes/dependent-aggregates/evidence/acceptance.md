# Acceptance: dependent-aggregates

2026-11-28: **deferred to the developer**, who was away and had granted delivery to the end. Not
skipped and not accepted: validation ends with a person (epic-delivery). No release is cut before
the developer has done what follows.

## What the developer validates

1. The scenarios (`features/*.feature`), accepted by the lead under the grant
   (`scenario-signoff.md`).
2. The delivery decisions D-1 to D-13 in `design.md`.
3. Two decisions left open by the end-of-epic review (D-13):
   - A session opened without `may_read` names cascaded parts in its errors (full reach,
     documented in the manual). Keep it fail-open, or log or refuse when `dependence` is given
     without `may_read`?
   - A part write answers `NotFound` for a missing whole even when the caller may not read that
     whole, so it discloses whether the whole exists. Accept it, or answer as if the whole were
     missing when it is unreadable?

## Scenario to test map

- `rp-metamodel`, `rp-generation`: `tests/unit/schema/test_schema_structure_dependence.py`,
  `tests/generator/unit/test_dependence_check.py`, `tests/generator/feature/` scenarios 10–11.
- `rp-aggregate-store`: `tests/unit/persistence/test_session_dependent_{write,diagnosis,cascade,adversarial}.py`,
  `tests/integration/store/test_dependent_aggregates.py` (IT-D1..IT-D5), `tests/feature/`
  scenarios 1–9.
- `rp-service-api`: `tests/unit/api/test_dependent_routes.py`, `test_dependent_delete_route.py`,
  `test_openapi.py`.
- `rp-uml-import`: `tests/generator/unit/test_uml_own_graph_generated.py`, `tests/generator/feature/`
  scenario 12.

## The demo to run (suggested)

With the toy service: create an Audit, two AuditResults and an AuditFinding; delete the Audit as a
caller with delete on the Audit only; see the parts gone and one activity with four removals; then
write an AuditResult naming the deleted Audit and see 404.
