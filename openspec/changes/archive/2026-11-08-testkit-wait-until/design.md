<!-- PLAN (design half). PLAN = this file + tasks.md. -->

> Derives from: EPIC `testkit-wait-until` (proposal.md), GitHub issue #24.

## Context

`wait_until` (`rdf_persistence/testkit/bootstrap.py:16`) polls `probe` every `POLL_SECONDS` (1 s)
until a deadline (`DEFAULT_TIMEOUT_SECONDS`, 180 s), treating `retry_on` errors (default
`(OSError,)`) as "not ready", and raises `TimeoutError` naming `what`. It is tested in
`tests/unit/test_testkit_bootstrap.py` with an injected sleep and clock, and used by the container
fixtures. `rdf_persistence/testkit/__init__.py` does not export it.

## Goals / Non-Goals

**Goals:** both helpers importable from `rdf_persistence.testkit` (DEC-1, DEC-2); the checklist and
the public API table name them.
**Non-Goals:** see the EPIC's No-gos.

## Decisions

- **PD-1**: `wait_until_async` lives beside `wait_until` in `bootstrap.py`, which already holds
  "plain helpers behind the container fixtures" and imports nothing heavy (DEC-3). Rejected: a new
  module for one function.
- **PD-2**: Signature:

  ```python
  async def wait_until_async[T](
      probe: Callable[[], Awaitable[T]],
      what: str,
      *,
      timeout: float = DEFAULT_TIMEOUT_SECONDS,
      retry_on: tuple[type[Exception], ...] = (OSError,),
      sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
      monotonic: Callable[[], float] = time.monotonic,
  ) -> T
  ```

  Same defaults and the same `TimeoutError` text as `wait_until`. Rejected: accepting both sync and
  async probes in one function (a type that hides which one the caller passes).
- **PD-3**: Both names are eager exports in `__init__.py` (imported at the top with the fakes), not
  lazy: `bootstrap.py` imports only the standard library (`os`, `time`, `collections.abc`,
`contextlib`, plus `asyncio` now). The lazy-import
  tests (`tests/unit/test_testkit_lazy_import.py`) prove the root stays light.
- **PD-4**: The timeout message is built by one private helper both functions call, so the two
  messages cannot drift.

## Algorithm / approach

```python
deadline = monotonic() + timeout
while monotonic() < deadline:
    try:
        result = await probe()
    except retry_on:
        result = None
    if result:
        return result
    await sleep(POLL_SECONDS)
raise TimeoutError(_timed_out(what, timeout))
```

Worked example (the issue's):

```python
listing = await wait_until_async(lambda: list_files(client, tenant), "the file listing",
                                 timeout=10, retry_on=())
```

Idempotency: both helpers only call the probe; they are as safe to repeat as the probe is.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| `asyncio.run(...)` inside `wait_until_async` | `await` the probe in the caller's loop | a test already runs inside an event loop |
| Real sleeps in the new tests | inject `sleep` and `monotonic` | testing rule 11 |
| Copy the loop text without sharing the message | share `_timed_out` (PD-4) | two messages would drift |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Probe never truthy | clock passes the deadline | `TimeoutError` naming `what` |
| Probe raises a `retry_on` error | `except retry_on` | treated as "not ready", polled again |
| Probe raises another error | not caught | propagates on that call |
| Caller passes a sync probe to the async helper | `await` of a non-awaitable raises `TypeError` | propagates; mypy flags it before |

## Risks / Trade-offs

- [Two near-identical loops] → kept to ~10 lines each; the shared message helper and parallel
  tests keep them in step.

## Open Questions

None.

## Review fixes (leader's decisions after the deep test and the five-lens review, 2026-11-08)

- **RF-1** (L2). The propagation test asserts the probe ran once and nothing slept.
- **RF-2** (L4). The async test helper is `_wait_async`, the twin of `_wait`.
- **RF-3** (L3). The `bootstrap.py` docstring says it also holds the public waiting helpers.
- Not taken: bounding a probe that never returns with `asyncio.timeout` (L1): both helpers share
  this limit today and the EPIC exports them unchanged; a later change may add it to both. A docs
  check that rule 11 names only exported helpers (L2): no such check exists for other pages.
