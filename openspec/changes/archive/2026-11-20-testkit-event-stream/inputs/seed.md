<!-- Secondary input, never groomed: GitHub issue #204 (meaningfy-ws/rdf-persistence), fetched 2026-11-20. The EPIC (../proposal.md) supersedes it. -->

# #204 testkit: open a tenant's event stream in-process

## Summary

The testkit offers no public way to open a tenant's event stream (`GET {prefix}/{tenant_segment}/{t}/rp-events`) in-process. A consumer cannot test that its access rules let a reader follow the stream without writing raw ASGI plumbing, which the toolkit keeps private in its own tests (`Follow` in `tests/unit/api/test_events_route.py`, `Following` in `tests/feature/test_events.py`).

## Context

- Consumer: MWB2 (mapping-workbench-v2), change `v2-01-toolkit-upgrade`, task 6.1 (a review follow-up: prove the consumer's access rules on the events route that `install_service` now adds).
- The consumer tests its app in-process over the testkit's fakes with an `httpx` client on `ASGITransport`. The refusals (no token: 401; no right on the tenant: the hidden tenant's 404) test fine that way. The positive case does not: `ASGITransport` waits for the end of the response, and the stream ends only when the follower leaves or `max_lifetime_seconds` (default 300) passes, so the test hangs.
- rdf-persistence commit: `c671fefb` (code of `v0.7.0`).

## What is missing

A testkit helper that opens the stream on an app built by `install_service`, returns the response head (status, headers) and, optionally, the first N events, then leaves; bounded by a timeout so a test never hangs. Without it, each consumer either copies the toolkit's private `Follow` class (forbidden by its own rules), rebuilds the app with short-lived `SseSettings` only for tests, or leaves the positive case untested.

## Expected behaviour / proposed capability

```python
from rdf_persistence.testkit import open_event_stream   # proposed name

async def test_a_reader_follows_the_tenant(app, token, tenant_id):
    opened = await open_event_stream(
        app,                                     # the FastAPI app install_service set up
        f"/api/libraries/{tenant_id}/rp-events",
        headers={"Authorization": f"Bearer {token}"},
        events=0,                                # how many events to wait for before leaving
        timeout=3.0,                             # seconds; raises TimeoutError, never hangs
    )
    assert opened.status == 200
    assert opened.headers["content-type"].startswith("text/event-stream")
    assert opened.events == []                   # parsed `id`/`event`/`data` records when events > 0
```

- Returns a small result (status, headers, events) as a generated or documented testkit type.
- Runs the app's lifespan if needed, sends `http.disconnect` after the head (or after `events` events), and cancels the app task.
- Raises `TimeoutError` naming the URL when the head or the events do not arrive in time.

## Why it belongs in rdf-persistence

The route is the toolkit's and every application that installs the service serves it, so every one that checks its access rules needs this. The toolkit already has the logic twice in its own tests; a consumer writing its own would copy it and drift from the route's behaviour (keep-alive comments, `Last-Event-ID`, the lifetime).

## Acceptance

- **Given** an app built by `install_service` and a token of a reader of tenant `t` **When** a test calls `open_event_stream(app, ".../t/rp-events", headers=…)` **Then** it returns status 200 and a `text/event-stream` content type within the timeout.
- **Given** a commit in tenant `t` after the stream opened **When** the helper waits for `events=1` **Then** it returns one event whose `id` is the activity's IRI.
- **Given** a caller with no right on `t` **When** the helper opens the stream **Then** it returns the refusal's status (404) without waiting for the timeout.
- **Given** a stream that sends nothing **When** `events=1` and `timeout=0.5` **Then** it raises `TimeoutError` naming the URL.

## Impact on the consumer

Not blocking the upgrade. The consumer keeps its two refusal tests; the positive case (a member follows the stream) waits for this helper and a lock refresh.


## Comments

