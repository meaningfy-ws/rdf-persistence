EPIC: consumer-gap-fixes (proposal.md, #304, #306, #311, #312). Decisions: DEC-1 to DEC-7; design.md D-1 to D-5.

> Derives from: `proposal.md`. Starts after `domain-values-and-fixes` merges its last PR.
> Review per stage: one pass (SMALL; P-0005 applies from MEDIUM).

## 1. A narrowed role keeps its multiplicity (#304), PR 1, branch `fix/narrowed-role-multiplicity`

- [ ] 1.1 Tests first: E1, E2, E3 (`design.md#stage-1-304-converter`) in
  `tests/generator/unit/test_uml_rules.py`. RED: `multivalued` missing from `B.slot_usage.p`.
- [ ] 1.2 Fix in `usage_of` (DEC-1, `design.md` D-5). Regenerate the toy. The golden diff may hold
  only explicit flags on slots whose usages differ (RISK-1). CHANGELOG **BREAKING** line. Accept:
  E1 to E3; `make test-changed check-quality`.
- [ ] 1.3 Lead: `make check-all`, one review pass, PR. This EPIC lands with it.

## 2. One path for grants (#306), PR 2, branch `fix/set-grants-roles`

- [ ] 2.1 Tests first: E4 to E8, E15, E19 in `tests/unit/tenancy/test_set_grants_roles.py`, plus one
  route test in `tests/unit/api/test_router.py` (`design.md#stage-2-306-grants`). RED: an undefined
  role is stored.
- [ ] 2.2 `Tenancy(rules=…)` as a required keyword, stored as `rules.with_iris(self._iris)` after `self._iris` is resolved, and wired in `kit.py`.
  The call goes in `set_grants`, after `get`, and the route's call goes (DEC-2, `design.md` D-4).
  Update the direct constructors in the tests and their role definitions. CHANGELOG **BREAKING**
  (constructor). The tenancy how-to gets its paragraph (RISK-2). Accept: E4 to E8, E15, E19;
  `make test-fast check-quality`.
- [ ] 2.3 Lead: `make check-all`, one review pass, PR.

## 3. `state_iri` is public (#311), PR 3, branch `fix/export-state-iri`

- [ ] 3.1 Tests first in `tests/unit/package/test_lazy_exports.py` (`design.md#stage-3-311-export`).
  RED: `ImportError`.
- [ ] 3.2 Lazy export, `__all__`, `make refresh-surface`, and the `howto/workflow.adoc` import (DEC-3).
  Accept: the test; `make check-docs`.
- [ ] 3.3 Lead: `make check-all`, one review pass, PR.

## 4. Absence in `find` and the listing (#312), PR 4, branch `fix/absent-filter`

- [ ] 4.1 `filter_absent` in `rp_persistence_services.yaml`, then `make generate` (DEC-6, `design.md` D-1).
- [ ] 4.2 Tests first: E9 to E14 and E16 to E18, in the files `design.md#stage-4-312-absence`
  names. RED: `find(..., s=None)` returns nothing.
- [ ] 4.3 `_filter`, `_items`, `list_request` with `absent` reserved, `_filtered`,
  `condition_patterns`, and `absent_patterns` in `core/domain/sparql.py` (DEC-4, DEC-5,
  `design.md` D-2, D-3). Accept: E9 to E18; `make test-fast check-quality`.
- [ ] 4.4 The `absent` parameter in `openapi.py` `_query_parameters`. `reference/http-api.adoc`:
  absence, the reserved names, `ifabsent`. CHANGELOG "Changed" (RISK-3, RISK-5). Accept:
  `make check-docs`.
- [ ] 4.5 Lead: `make check-all`, `make test-containers`, one review pass, and a PR that flags
  DEC-5 for the owner's review.

## 5. Close

- [ ] 5.1 Scenario-map rows for the new tests (each stage adds its own).
- [ ] 5.2 After the last merge: reconcile the proposal, archive, and ask for a release (RISK-4).
  Comment on #304, #306, #311 and #312 with the version.

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 2.1 · [ ] 2.2 · [ ] 2.3 · [ ] 3.1 · [ ] 3.2 · [ ] 3.3 ·
  [ ] 4.1 · [ ] 4.2 · [ ] 4.3 · [ ] 4.4 · [ ] 4.5 · [ ] 5.1 · [ ] 5.2

## Verification

Each stage: its E-rows go red, then green; `make check-all` before each PR; `make test-containers`
for stage 4; `openspec validate consumer-gap-fixes --strict`; the PLAN gated (`evidence/clarity-gate.md`).
