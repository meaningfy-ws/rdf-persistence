# Acceptance: aggregate-guards

SMALL appetite: the demo is offered and the developer may skip it.

- **2026-11-24, not run.** The developer asked the lead to "carry on, merge and close the epic"
  after stage 2. The lead offered the demo in the closing summary (a rule reading a referenced
  book through `POST /loans`, and a `DELETE` refused with a 409 `refused` problem). If the
  developer asks for it, the verdict goes here.
- What verified the use cases instead: T1–T17 at unit and API level, the T6 integration test
  against the store, and `make check-all` with `make test-containers` green on each stage's PR
  head (#334, #346).
