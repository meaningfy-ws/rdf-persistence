EPIC: reference-filters (proposal.md, #308). Decisions: DEC-1 to DEC-8; design.md D-1 to D-6.

> Derives from: `proposal.md`. Starts after `consumer-gap-fixes` stage 4 (#312) merges (RISK-1).
> One stage, one PR, branch `feat/reference-filters` (DEC-8). Review (MEDIUM, P-0005): the one
> stage is also the epic's end, so it gets the full review (L1, L2 and L3 as separate passes, then
> L4 and L5 as one pass) and one stage check.

## 1. Filters through references, PR 1

- [ ] 1.1 Lead, at stage start: `make reindex` and GitNexus impact on `condition_patterns`,
  `Listings._filtered` and `graph_iri`. Re-read the merged stage 4 code (`condition_patterns`,
  `_filtered`, the `Condition` model). Revise D-2 and D-4 in `design.md` before any code if it
  diverged (RISK-1). A HIGH or CRITICAL impact goes to the developer.
- [ ] 1.2 Model: `condition_via` on `Condition` in `rp_persistence_services.yaml`, then
  `make generate` (DEC-1, D-1). Accept: the generated `Condition(via=[…])` builds, and
  `make test-fast` stays green.
- [ ] 1.3 Tests first for the renderer: `hop_patterns` in `tests/unit/core/test_sparql.py`, and
  E14 (path-less rendering unchanged, as literals) in `tests/unit/persistence/test_listing_query.py`
  (`design.md#tests-first-all-red-before-the-code`). E14's literals (the `condition_patterns`
  strings and a whole `listing_query` text with hidden graphs) are captured from the code before
  any change. RED: `hop_patterns` does not exist.
- [ ] 1.4 `GRAPH_SUFFIX` in `iris/domain/layout.py`. `hop_patterns` in `core/domain/sparql.py`. The
  `condition_patterns` dispatch with `hidden`, and `listing_query` passing `plan.hidden_graphs`
  (D-2, D-3). Accept: 1.3 green; `make test-fast check-quality`.
- [ ] 1.5 Tests first for resolution and behaviour:
  - S2b, E2 to E13 and E16 in `tests/unit/persistence/test_listing.py`.
  - S1, S2, S3, S3b, S6, S9 and S10 in `tests/unit/persistence/test_listing_query.py`.
  - S4 in `tests/unit/api/test_listing_routes.py`.
  - S1 and S3b in `tests/integration/api/test_listing.py`.
  - S8 in `tests/integration/store/test_session.py`.

  RED: `BadQuery` "has no slot 'written_by.label'".
- [ ] 1.6 Path resolution in `Listings._filtered` with `_hop` and `MAX_HOPS = 3`; the absence
  refusal (D-4). The `find` docstring (D-5). Accept: 1.5 green; `make test-fast check-quality`.
- [ ] 1.7 Docs:
  - The OpenAPI listing description (D-6): a `description` keyword on `route_options`, carried by
    `RouteDocs` into `add_api_route`, and set only by `AggregateOpenApi.listing`. Then
    `make refresh-served-golden`. The diff may hold only that description, once per aggregate
    listing.
  - `reference/http-api.adoc`: the path syntax, the cap, DEC-4's independence, the access rule
    (DEC-5) and the refusals.
  - CHANGELOG "Added".

  Accept: `make check-docs`.
- [ ] 1.8 Lead: `make check-all`, `make test-containers` (the Fuseki rows), the full review (P-0005), the
  stage check and the fix pass, then the PR. This EPIC lands with it.

## 2. Close

- [ ] 2.1 Scenario-map rows for the new tests (`make refresh-map`).
- [ ] 2.2 After the merge: reconcile the proposal, archive, ask for a release, and comment on #308
  with the version (RISK-4).

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 1.4 · [ ] 1.5 · [ ] 1.6 · [ ] 1.7 · [ ] 1.8 · [ ] 2.1 · [ ] 2.2

## Verification

- The S and E rows go red, then green.
- `make check-all` and `make test-containers` before the PR.
- `openspec validate reference-filters --strict`.
- The PLAN is gated (`evidence/clarity-gate.md`).
