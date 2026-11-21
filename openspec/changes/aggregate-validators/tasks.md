EPIC: aggregate-validators (proposal.md), issue #240. Decisions: DEC-1 to DEC-5; design.md PD-1 to PD-9; owner answers in inputs/qa.md.

Every task: the failing test first, in the tier named; task gate `make test-changed check-quality`
(`make test-fast check-quality` for 1.3, a port change); commit body `Refs: aggregate-validators
<task> <PD>`. Builders never commit; the lead does. One stage, one PR; it merges on green CI
(P-0013). Test ids T-n / A-n are design.md's test table.

## 1. Stage 1: aggregate validators

- [ ] 1.1 Registration (PD-1, PD-2). Unit, first, in
  `tests/unit/collaboration/test_aggregate_validators.py`: T-1, T-2, a non-callable rule →
  `TypeError`, an empty mapping selects nothing. Then `collaboration/services/aggregate_validators.py`
  with the two types and `AggregateValidators` (keys checked with `root_classes`, mixins and toolkit
  classes refused, `class_descendants(mixins=False)`), and the class IRI → rules map.
- [ ] 1.2 Selection and running (PD-3, PD-7), after 1.1. Unit, first, same file: T-3, T-4, T-5.
  Then the selection over all root types and `run_aggregate_validators`.
- [x] 1.3 Session read check (PD-4), a port change. Unit, first, in
  `tests/unit/persistence/test_session_may_read.py`: a session opened with `may_read` exposes it;
  without, `None`. Then the keyword on `open_session`, `Tenancy.tenant_session` and the session.
  Accept: `make test-fast check-quality` green.
- [ ] 1.4 Reader (PD-5), after 1.1 and 1.3. Unit, first, in the 1.1 file: T-6, T-7. Then the reader
  (per `prepare`, `context.collected`, `not_aggregates`, `heads`).
- [ ] 1.5 In the guard (PD-6, PD-8, PD-9), after 1.2 and 1.4. Unit, first, same file: T-8, T-9,
  T-10, T-11, a refused add leaves no graph, a refused replace leaves the stored version, a refused
  unit-of-work commit raises `InvalidBody`. Then `WriteGuards(..., validators=)` (keyword with an
  empty default, so existing constructions in tests keep working) and the call at the end of
  `prepare`, with the decoding of `new` and `old`.
- [ ] 1.6 Wiring (PD-2, PD-4), after 1.5. API tests, first, in
  `tests/unit/api/test_aggregate_validators_api.py`: A-1 to A-7 (every scenario of
  `specs/rp-service-api/spec.md`). Then the keyword on `install_service` and `ServiceKit`
  (`tests/toy_service.py` too); `DocumentApi.create` / `replace` take the `CallerAccess` (the
  routes at `router.py:409-427` and the tenant-root PUT at :267 pass it); `Aggregates.create` /
  `replace`, `kit.collaboration` and `Tenancy.rename` take and pass `may_read` (`DocumentApi.set_label` passes it). Accept: all pass;
  `tests/fixtures/public-surface.json` and `tests/unit/test_public_api.py` list the two new exports.
- [ ] 1.7 Docs, after 1.6. `docs/modules/ROOT/pages/user-manual/access.adoc` (beside
  `root_validators`): the signature, the reader and who it answers for, which writes run rules and
  which do not, the order limit inside a unit of work, RISK-2, RISK-4, RISK-5;
  `architecture/data-flows.adoc` (the guard's last step); `partials/reference/public-api.adoc`.
  Accept: `make check-docs` green.

## 2. Roadmap

1.1 → 1.2; 1.3 in parallel; 1.4 after 1.1 and 1.3; 1.5 after 1.2 and 1.4; 1.6; 1.7. Lead gates:
`make check-all`, `make test-containers` (the guard on the real store in the integration tier);
review by one pass at SMALL (P-0005).

## 3. Tests moved or rewritten

None. Existing `WriteGuards(...)` and `open_session(...)` call sites keep working (the new keywords
have defaults); they still run in the unit lane and prove what they proved.
