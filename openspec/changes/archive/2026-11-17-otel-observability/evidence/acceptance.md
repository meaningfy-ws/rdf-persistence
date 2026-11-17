# Acceptance: otel-observability

**Verdict:** demo skipped.

- **Who:** the developer.
- **When:** 2026-11-17, after PR #152 (stage 2) was opened.
- **Why:** the developer's word in the epic session: "I would skip the demo in this epic, just
  proceed forward with the remaining tasks and close the epic".
- **What stands in for it:** the feature file `tests/feature/observability.feature` (nine spec
  scenarios on the toy service), the container test TC-28 (a Redis publish and receive joined in
  one trace), the local gates on the merged head (PR #152: `make check-all` 7369 passed,
  `make test-containers` 261 passed) and the stage checkers' pass verdicts.
- **Validation still open:** a person seeing traces and logs of a real consumer in a backend.
  The first consumer (MWBv2) does this when its change names this one (AGENTS.md, D-12).
