# Acceptance: consumer-test-gaps

**Status:** offered, awaiting the developer's verdict (SMALL: the developer may skip it).

**Success measure (EPIC):** the consumer's three workarounds become unnecessary: its `times=2`
fault (#319), its `store.update` wrapper (#323) and its label-less referrer display (#320); and a
redrawn role keeps its own cardinality (#332).

**What the delivery already shows (verification, not validation):**

- #319 and #323: `tests/feature/testkit_faults.feature` over the toy service with its lifespan
  entered. E1 gives 503 on 20 runs inside `relay.paused()`, and the woken relay then marks each
  activity. E2 has two concurrent replaces under `hold("update", until=2)`: one 200, one 409
  `conflict`, and the winner's version stored.
- #320: `tests/unit/api/test_delete_in_use.py`. A 409 `in-use` and a referrers listing whose items
  carry `referrer_rp_path` and `referrer_id`, then a `GET` built from them answers 200 (E9).
- #332: `tests/generator/unit/test_uml_rules.py` E15–E23, through `SchemaView.induced_slot`.
  `make test-containers` passed 366 on 2026-11-25.

**Demo, if taken:** in the consumer's v2-03 branch, drop `times=2`, the `store.update` wrapper and
the label-less display, pin this release, and run its concurrent-write, fault and referrer
scenarios.

**Verdict:** _the developer's: accepted / rejected (what is wrong) / skipped (who, why, date)._
