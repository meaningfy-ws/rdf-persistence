EPIC: test-debt-paydown (proposal.md). Decisions: design.md PD-1 to PD-15, DEC-1 to DEC-4.

Every task: test-first where it adds a test; task gate `make test-changed check-quality`
(`make test-fast check-quality` after `domain` or a port); commit body `Refs: test-debt-paydown
<task> <PD>`. Builders never commit; the lead does.

## 1. Stage 1: test structure (tests only)

- [ ] 1.1 Move the tests (PD-11 moves): tooling tests and `test_private_transaction_pieces.py` to
  `tests/unit/tooling/`, package tests to `tests/unit/package/`; `Makefile` and
  `tests/changed.py` updated (rule 11's `root_unit_tests()` maps a root-package change to
  `tests/unit/package/`; `test_changed.py`'s own-path assertion follows its move); the moved files' paths rewritten in the `test` column of
  `tests/audit/scenario-map.csv` with Edit, before the refresh. Accept: `make test-fast` collects
  the same count as before the move; `make refresh-map` exit 0 with "Removed rows (0)".
- [ ] 1.2 Cross-test imports (PD-8), after 1.1: move every name of `inputs/probes/cross_imports.out`
  to its home; then add `tests/unit/tooling/test_no_cross_test_imports.py`. Accept: the guard
  passes, and its own test shows it fails on each of the three planted forms PD-8 names.
- [ ] 1.3 Rule-5 replacements without production change (PD-1: `test_service_kit` spy,
  `test_migrate_dataset` x3, the adversarial `CountingDataset`, `test_generation_inputs` x2,
  `test_freshness` x2) and the three recorded exceptions in `testing.adoc`. Accept: `grep
  monkeypatch.setattr` in those files lists only the recorded exceptions (and exception 4 if the
  SparqlError data route fails, reported).
- [ ] 1.4 Waits (PD-3, PD-4) in `test_events_route.py` and `test_relay.py`. Accept: no
  `timeout=` expecting `TimeoutError` left in `test_events_route.py`; with
  `PYTEST_ADDOPTS="--durations=0" make test-changed`, no test of either file is above 0.2 s.
- [ ] 1.5 P-20 and P-31 (PD-9, PD-10). Accept: 17 token cases, 1 email case; the hand
  mutations listed in the report, each caught.
- [ ] 1.6 Under-the-floor remainder (PD-11 except the moves): comment form, docstrings,
  `test_tenant_move.py` to `tests/unit/domain/` (and `setup.cfg`), marker completeness, Hypothesis
  `-n 2`, `utc_now` awareness, `listing_shelf` models and personas, conftest constants, dead code.
  `test_tenant_move.py`'s map rows are rewritten to its new path first, as in 1.1.
  Accept: `grep -rniE "equivalence class|\bstage [0-9]|\btask [0-9]+\.[0-9]+" tests --include=*.py`
  is empty (42 plan-number docstrings and 39 comments today);
  `make refresh-map` exit 0 with "Removed rows (0)";
  `make check-architecture` passes with `test_tenant_move.py` under the domain contract.
- [ ] 1.7 Lead: stage-1 full gates (`make check-all`, `make test-containers`), one L2+L3 review
  pass (P-0005), fixes, ticks.

## 2. Stage 2: production seams and clean-ups

- [ ] 2.1 `Relay.paused()` (PD-2) with its three unit tests, then TC-37a and TC-38 use it. Accept:
  no `monkeypatch` in `test_events_route.py`; the `rp-events` scenarios pass.
- [ ] 2.2 Fuseki branch (PD-5). Accept: `test_data_plane_statuses_map_to_errors` passes unchanged.
- [ ] 2.3 Auth (PD-6): two tests, `Basic <valid jwt>` and `"Bearer "` with a permissive verifier
  stub; both are 401s today. Accept: each fails when its half of the guard is removed by hand.
- [ ] 2.4 Shapes cache (PD-7). Accept: the median of 7 `ToyService()` timings drops by ≥ 25 %
  (before and after on one checkout); `test_validating_leaves_the_cached_shapes_unchanged` passes;
  a new test: two same-size rewrites of a shapes file in `tmp_path`, each `Documents` gets its own.
- [ ] 2.5 `event_bus_conformance` `poll_seconds` (PD-15, rp-testkit delta). Accept: both delta
  scenarios pass as the two tests PD-15 names; the Redis test passes `poll_seconds=0.05`.
- [ ] 2.6 Lead: the `rp-messages` delta (DEC-1) checked against `Transaction`'s docstring and
  `test_an_empty_commit_does_not_spend_the_command_for_the_real_one_after_it`; stage-2 full gates;
  one L2+L3 pass; fixes.

## 3. Stage 3: domain mutation

- [ ] 3.1 Lead: `make mutation`; the survivor list in `inputs/survivors-before.md`.
- [ ] 3.2 Kill groups C, R, S, T in `test_exceptions.py`, `test_sparql*.py`,
  `test_tenant_move.py`, in parallel with 3.3.
- [ ] 3.3 Kill groups D', E, G, H, H', I, J, K, L, M, N (7), O, P, Q in `test_iris*.py`; L'
  timeboxed (PD-12).
- [ ] 3.4 `tests/audit/equivalent-mutants.md`: every remaining survivor with its one-line reason.
  Accept: `make mutation`'s survivors = the file's list, exactly.
- [ ] 3.5 Lead: full gates, the final review (the appetite's full set), fixes, the PR, CI green
  (PD-14), merge, acceptance by the owner, archive.

## Roadmap

1.1 → 1.2 → (1.3 ∥ 1.4 ∥ 1.5) → 1.6 → 1.7 → (2.1 ∥ 2.2 ∥ 2.3 ∥ 2.4 ∥ 2.5) → 2.6 → 3.1 →
(3.2 ∥ 3.3) → 3.4 → 3.5

## Verification

`make check-all`, `make test-containers` and `make mutation` pass, the mutation survivors match
`tests/audit/equivalent-mutants.md`, `openspec validate test-debt-paydown --strict` passes, and the
PR's CI is green before the merge.
