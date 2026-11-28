> Derives from: EPIC `write-rules-followups` (proposal.md); issue #455.

## 1. Stage 1 (one PR)

Wave A runs 1.1, 1.2 and 1.3 in parallel (disjoint files); the lead does 1.4. Wave B is 1.5.

Each task's decisions are the `design.md` Decisions bullets named (PD-n).

- [ ] 1.1 Refusal registration and status (PD-1, PD-2). Files: `api/entrypoints/kit.py`,
  `problems.py`, `service.py`, `tests/unit/api/test_rule_refusal.py`. Acceptance: S1, S2
  (rp-service-api delta), the existing refusal tests green.
- [ ] 1.2 `find` in the rule readers (PD-3 to PD-6). Files:
  `collaboration/services/aggregate_validators.py`, `persistence/services/session.py` (docstring
  only), `testkit/fakes.py`, `testkit/reader_conformance.py`, `tests/unit/testkit/test_fake_reader.py`,
  the reader's unit tests (`tests/unit/collaboration/`), `user-manual/{access,files,test}.adoc`.
  Acceptance: S3, S4, S5; the conformance kit green on both readers. The adversarial tester follows.
- [ ] 1.3 Generator (PD-7 to PD-9). Files: `rdf_persistence_generation/extensions/pydantic_split.py`,
  new `technical_checks.py`, `typescript.py`, the generator tests that import the moved names.
  Two commits: the move (no behaviour change), then the enum check. Acceptance: S6; generator
  tests green.
- [ ] 1.4 Schema cache and `hbreader` (PD-10, lead). Files: `schema_cache.py`, `pyproject.toml`,
  `uv.lock`, a unit test beside the cache's tests. The lead runs `uv lock`, `uv sync`, then
  `make test-seed`. Acceptance: S7.
- [ ] 1.5 `ban_reading` once (PD-11), after 1.1 and 1.2. Files: `tests/scene.py`,
  `tests/unit/api/test_aggregate_validators_api.py`, `tests/unit/api/test_rule_refusal.py`,
  `tests/unit/api/test_delete_in_use.py`, `tests/feature/test_consumer_write_rules.py`.
  Acceptance: those tests green, one definition.
- [ ] 1.6 CHANGELOG (PD-12, lead), after 1.1 to 1.3.

## Roadmap

- [ ] 1.1 ∥ 1.2 ∥ 1.3 ∥ 1.4 · [ ] tester after 1.2 · [ ] 1.5 · [ ] 1.6 · [ ] review (one pass)
  ∥ checker · [ ] fix to the floor · [ ] `make check-all` · [ ] PR

## Verification

Each builder: `make test-changed check-quality`. The lead: `make check-all` on the rebased head;
the checker runs `make check-docs`. The PLAN is gated ≥ 9/10 (`evidence/clarity-gate.md`).
