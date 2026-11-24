# Acceptance: aggregate-guards

SMALL appetite: the demo is offered and the developer may skip it.

- **Skipped, 2026-11-24, by the developer** ("skip the demo and cut the release"), after the lead
  offered it in the closing summary: a rule reading a referenced book through `POST /loans`, and a
  `DELETE` refused with a 409 `refused` problem.
- What verified the use cases instead: T1–T17 at unit and API level, the T6 integration test
  against the store, `make check-all` with `make test-containers` green on each stage's PR head
  (#334, #346), and the review findings closed as tests in `aggregate-guards-test-gaps`.
