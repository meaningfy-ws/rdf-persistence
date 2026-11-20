<!-- Parents: issue #204 (inputs/seed.md); openspec/specs/rp-testkit, rp-events. Serves: one
     deferred test of the archived MWB2 v2-01-toolkit-upgrade, task 6.1 (D-12); not urgent.
     Seeds: inputs/seed.md. -->

# EPIC: testkit helper to open a tenant's event stream in-process

## Appetite

**TINY.** The logic already exists twice in the toolkit's own tests. It becomes one public testkit
function.

## Why

A consumer cannot test that a reader may follow `.../rp-events` in-process. `ASGITransport` waits
for the end of a stream that never ends, so the test hangs. The toolkit's own `Follow` and
`Following` helpers are private.

## Solution outline

`rdf_persistence.testkit.open_event_stream(app, url, headers=…, events=0, timeout=3.0)` returns the
status, the headers and the first `events` parsed events, then disconnects and cancels the app task.
On a timeout it raises `TimeoutError` naming the URL. A refusal (401/404) returns at once. The
toolkit's own tests switch to it, and both private helpers are deleted.

## Key decisions

- **DEC-1:** one public function replaces both private helpers. Rejected: publishing `Follow` as a
  class.
- **DEC-2:** the result is a small frozen dataclass in `testkit` (status, headers, events).

## Rabbit-holes

- Lifespan handling: the function runs the app's lifespan only when the app has not started it.

## No-gos

- No reconnect, no `Last-Event-ID` resume helper, no client for production use.

---

## What Changes

- `rdf_persistence/testkit`: `open_event_stream` and its result type.
- `tests/unit/api/test_events_route.py` and `tests/feature/test_events.py` use it, and their private
  helpers go.

## Capabilities

### Modified Capabilities

- `rp-testkit`: a public helper to open a tenant's event stream.

## Impact

Testkit public surface (`assert_public_imports` list), two test modules, the testkit how-to.
