EPIC: listing-contains-filter (proposal.md, issue #203). Decisions: design.md PD-1 to PD-12, DEC-1, DEC-2.

> Derives from: EPIC `listing-contains-filter`.

Every task: the failing test named first, in its tier; task gate `make test-changed check-quality`
(`make test-fast check-quality` where marked: `domain` or a port changed); commit body
`Refs: listing-contains-filter <task> <PD>`. Builders never commit; the lead does. One stage
(SMALL); tasks run in order, they share `listing.py`.

## 1. Stage 1: the contains filter

- [ ] 1.1 Model and parsing (PD-1, PD-2), unit: TC-01 first, failing. Add `filter_contains` to
  `rp_persistence_services.yaml`, `make generate`, then `list_request`. The served TypeScript
  golden follows with `make refresh-served-golden` (review the diff: `Filter` and `Condition`
  gain `contains?: boolean` only). Accept: TC-01 passes; `make check-generated` clean after the
  lead's commit.
- [ ] 1.2 Rendering (PD-5), unit, `domain`: TC-04 first, failing. `contains_patterns` in
  `core/domain/sparql.py`. Gate: `make test-fast check-quality`.
- [ ] 1.3 Plan, one renderer and the routes (PD-3, PD-4, PD-6), unit: TC-02, TC-03, TC-05, TC-06,
  TC-08 and TC-09 first; all fail except TC-09's tenant case, which guards today's refusal.
  `holds_text` in `schema_structure.py`; `Listings.plan`; `condition_patterns` and its three uses
  in `listing.py` and `session.py`. Gate: `make test-fast check-quality`. Accept: all pass.
- [x] 1.4 `Contains` and `find` (PD-7, PD-10), unit: TC-07 first, failing. The generated
  `Contains` class in `rp_persistence_services.yaml`, `make generate`, `make refresh-served-golden`
  (diff: `interface Contains` only); `_filters`, `rdf_persistence.__all__`, `NAMES` 149, `make refresh-surface` (diff: one added name).
  Accept: TC-07 and `tests/unit/test_public_surface.py` pass.
- [x] 1.5 OpenAPI (PD-8), unit: TC-10 first, failing. `<slot>~` parameters in `openapi.py`;
  `make refresh-served-golden` (diff: only the `~` parameters). Accept: TC-10 and
  `tests/unit/api/test_openapi_served.py` pass.

## 2. Docs, spec and gates

- [ ] 2.1 Docs (PD-9): `api.adoc#serving`, `http-api.adoc#listings`, the docstrings. The
  `rp-aggregate-store` delta (PD-11) is already in the change.
  Accept: `make check-quality` (holds `check-docs` and `openspec validate --all --strict`).
- [ ] 2.2 Lead: IT-1 and IT-2 rows in `tests/integration/api/test_listing.py`; `make check-all`,
  `make test-containers`, `make check-types` (IT-3); `make refresh-map` exit 0 with the new tests
  mapped to the delta scenarios as design.md PD-12's table says; the SMALL review set
  (`docs/modules/ROOT/pages/develop/agents.adoc#challenge`); fixes; ticks.

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 1.4 · [ ] 1.5 · [ ] 2.1 · [ ] 2.2

## Verification

TC-01 to TC-10 in `make test-fast`, IT-1 to IT-3 in `make test-containers` and `make check-types`,
`openspec validate --all --strict`, clarity gate ≥ 9/10 (`evidence/clarity-gate.md`).
