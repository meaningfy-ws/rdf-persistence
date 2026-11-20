<!-- Parents: issue #204 (inputs/seed.md); openspec/specs/rp-testkit, rp-events. Serves: one
     deferred test of the archived MWB2 v2-01-toolkit-upgrade, task 6.1 (D-12); not urgent.
     Seeds: inputs/seed.md. -->

# EPIC: testkit helper to open a tenant's event stream in-process

## Appetite

**SMALL.** The logic already exists in the toolkit's own tests. It becomes one public testkit
function with generated result records, and three test modules switch to it.

> Re-shaped 2026-11-20 by the owner: TINY → SMALL (the PLAN found generated records, a lifespan
> flag and a third test module; inputs/qa.md).

## Why

A consumer cannot test that a reader may follow `.../rp-events` in-process. `ASGITransport` waits
for the end of a stream that never ends, so the test hangs. The toolkit's own `Follow` and
`Following` helpers are private.

## Solution outline

`rdf_persistence.testkit.open_event_stream(app, url, headers=…, events=0, timeout=3.0)` returns the
status, the headers and the first `events` parsed events, then disconnects and cancels the app task.
On a timeout it raises `TimeoutError` naming the URL. A refusal (401/404) returns at once. The
toolkit's own tests switch to it, and the private helpers' stream plumbing is deleted (amended
2026-11-20 by the owner: `Following` stays as the scenario's state holder; inputs/qa.md).

## Key decisions

- **DEC-1:** one public function replaces both private helpers. Rejected: publishing `Follow` as a
  class.
- **DEC-2:** the result types `OpenedStream` (status, headers, events) and `StreamEvent` are
  generated from LinkML (`rp_testkit.yaml`), per AGENTS.md principle 2. Replaced 2026-11-20 by the
  owner; it said "a small frozen dataclass in `testkit`", which the toolkit's model guard refuses
  (inputs/qa.md).

## Rabbit-holes

- Lifespan handling: the function runs the app's lifespan only when the app has not started it.

## No-gos

- No reconnect, no `Last-Event-ID` resume helper, no client for production use.

---

## What Changes

- `rdf_persistence/testkit`: `open_event_stream`; `rp_testkit.yaml`: its generated result records.
- `rdf_persistence/api/entrypoints/service.py`: the toolkit's lifespan sets and clears the flag
  `app.state.rp_lifespan_started` (added 2026-11-20 by the owner, OPEN-2; inputs/qa.md).
- `tests/unit/api/test_events_route.py`, `tests/unit/api/test_service_kit.py` and
  `tests/feature/test_events.py` use it; `Follow`, `Block` and `parsed` go, `Following` loses its
  stream plumbing.

## Capabilities

### Modified Capabilities

- `rp-testkit`: a public helper to open a tenant's event stream.

## Impact

Testkit public surface (`__all__`), three test modules, the toolkit's lifespan flag, the testkit
how-to.
