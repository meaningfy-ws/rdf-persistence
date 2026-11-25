EPIC: consumer-test-gaps (proposal.md, #319, #320, #323, #332). Decisions: DEC-1 to DEC-6; design.md D-1 to D-8.

> Derives from: `proposal.md`. No dependency on in-flight work: the stages share no code.
> Review per stage: one pass (SMALL; P-0005 applies from MEDIUM).

## 1. Testkit: aimed faults and held writes (#319, #323), PR 1, branch `feat/testkit-hold`

- [x] 1.1 Tests first: E3 to E8 and E4b in `tests/unit/testkit/test_fake_store.py`; E1 and E2 in
  `tests/feature/testkit_faults.feature` with `test_testkit_faults.py`, over the toy service with
  the lifespan entered explicitly so the relay is live (`design.md#stage-1-testkit-319-323`).
  RED: `FakeStore` has no `hold`.
- [x] 1.2 `FakeStore.hold`: one future per waiter, release in order, release on every exit
  (DEC-2, `design.md#decisions` D-2, D-3), with a docstring that names RISK-3. Accept: E1 to E8,
  E4b; `make test-changed check-quality`.
- [x] 1.3 `user-manual/test.adoc`: "Aim a fault at the request" (`relay.paused()`,
  `design.md#decisions` D-1) and "Hold concurrent writes" (`hold`, `design.md#risks` RISK-3). The examples are the feature test's code. Public-surface
  snapshot (`make refresh-surface`) if `hold` shows there. Accept: `make check-docs`.
- [x] 1.4 Lead: `make check-all`, one review pass, PR. This EPIC lands with it.

## 2. API: a referrer says where to read it (#320), PR 2, branch `feat/referrer-location`

- [x] 2.1 `referrer_rp_path` and `referrer_id` on `Referrer` in `rp_collaboration_services.yaml`
  (`design.md#decisions` D-4); `make generate`; refresh the golden TypeScript and OpenAPI fixtures
  (RISK-2).
- [x] 2.2 Tests first: E9 to E14 in the files that `design.md#stage-2-api-320` names (a new
  `tests/unit/collaboration/test_referrer_location.py` for `located`). RED: the fields are missing.
- [x] 2.3 `Iris.aggregate_id_of` (D-5); `located` in `referrer_naming.py`; `_listed(…, locate)`;
  `in_use_problem` and `install_problem_handlers(…, locate=None)`, wired in `service.py`
  (`design.md#decisions` D-6).
  Accept: E9 to E14; `make test-fast check-quality`.
- [x] 2.4 Docs: the `in-use` problem and the referrers listing in `reference/http-api.adoc` name
  both fields and when they are absent. CHANGELOG "Added". Accept: `make check-docs`.
- [ ] 2.5 Lead: `make check-all`, one review pass, PR.

## 3. Generator: a redrawn role keeps its own cardinality (#332), PR 3, branch `fix/narrowed-cardinality`

- [ ] 3.1 Tests first: E15 to E23 in `tests/generator/unit/test_uml_rules.py`, each through
  `SchemaView.induced_slot` too (`design.md#stage-3-generator-332`). RED: E15's induced minimum is 2.
- [ ] 3.2 `cardinality_unbounded` in the `UmlRule` enum of `rp_generation.yaml`; `make generate`.
- [ ] 3.3 `own_minimum`, `own_maximum` and `usage_of` (`design.md#decisions` D-7); `share(…,
  parent_of)` and the problem on the derived ancestor bound (D-8), with `parent_of` passed from
  `convert.py`'s `_lay_out`. Regenerate the toy. The golden diff may hold only explicit
  cardinalities on slots whose usages differ (RISK-1). Accept: E15 to E23; `make test-changed
  check-quality`.
- [ ] 3.4 `howto/uml-to-linkml.adoc`: the rule row and the fix advice (RISK-4). CHANGELOG
  "Fixed" (RISK-1, RISK-4). Accept: `make check-docs`.
- [ ] 3.5 Lead: `make check-all`, `make test-containers` (the generator e2e), one review pass, PR.

## 4. Close

- [ ] 4.1 Scenario-map rows for the new tests (each stage adds its own).
- [ ] 4.2 After the last merge: reconcile the proposal, archive, and ask for a release (DEC-6).
  Comment on #319, #320, #323 and #332 with the version, and tell the consumer which workaround
  each one removes.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 2.1 · [x] 2.2 · [x] 2.3 · [x] 2.4 · [ ] 2.5 ·
  [ ] 3.1 · [ ] 3.2 · [ ] 3.3 · [ ] 3.4 · [ ] 3.5 · [ ] 4.1 · [ ] 4.2

## Verification

Each stage: its E-rows green, `make check-all`, one review pass. The tests moved or rewritten:
none. Every test here is new, and the existing `test_delete_in_use.py` and
`test_collaboration_readable_referrers.py` cases stay green in `make test-fast` (the fields are
optional).
