# Acceptance: testkit-event-stream

- **Verdict:** accepted by the developer, 2026-11-20.
- **What was shown:** `tests/unit/api/test_open_event_stream.py` run against the toy service built
  by `install_service`, 5 passed:
  - a reader follows the stream: 200 and `text/event-stream`;
  - one event: its `id` is the activity's IRI;
  - a caller with no right on the tenant: 404 without waiting for the timeout;
  - a silent stream: `TimeoutError` naming the URL;
  - the file uses only the testkit's public names.
- **Context:** both full-gates runs were green (PR #213 body). One review pass, with W1 accepted as
  D-8. Follow-ups: #214 and #215.
