# Acceptance: aggregate-validators

- **Date:** 2026-11-21.
- **Who:** the lead, in an epic session the coordinating session opened for this EPIC; the developer was
  not in it.
- **Shown:** every signed-off scenario of `specs/rp-service-api/spec.md` (#246, #248) runs as an API-tier
  test in `tests/unit/api/test_aggregate_validators_api.py` (A-1 to A-7; traceability in
  `tests/audit/scenario-map.csv`), green in `make check-all` and on the real store in
  `make test-containers`.
- **Verdict:** accepted by the developer on 2026-11-21, after the merge (#266), without a demo: the
  developer waived it on the evidence above.
- **Open:** the first consumer's own rules (the rule #240 asks for) are written in the
  consumer, against the released toolkit.
