<!-- PLAN (design half). PLAN = this file + tasks.md. Parent EPIC: testkit-event-stream (proposal.md,
     DEC-1, DEC-2). Issue #204. -->

> Derives from: EPIC `testkit-event-stream` (proposal.md, DEC-1, DEC-2). Appetite SMALL
> (re-shaped from TINY by the owner, 2026-11-20). OPEN-1 to OPEN-4 answered: inputs/qa.md.

## Context

- The events route (`rdf_persistence/api/entrypoints/sse.py`, `rp-events`) streams until the
  follower leaves, the hub closes its queue, access is lost, or the first wake after
  `max_lifetime_seconds` (`events/services/event_stream.py`). `httpx.ASGITransport` waits for the
  response to end, so an in-process test of a following reader hangs.
- The ASGI plumbing exists once, in `Follow` (`tests/unit/api/test_events_route.py:51-141`), with
  `Block`/`parsed` (`:34-48`). `Following` (`tests/feature/test_events.py:228`) is the scenario
  context of `events.feature`: it holds `Follow` streams across steps but has no plumbing of its
  own. A **third user** the EPIC does not name: `tests/unit/api/test_service_kit.py:68,752` imports
  `follow` and `parsed` and reads a raw keep-alive block.
- Wire format (FastAPI 0.162 `format_sse_event`): comment lines first (`: keep-alive` from the
  toolkit, `: ping` from FastAPI's own 15 s inserter), then `event:`, `data:` (one line per line),
  `id:`, each block ending in `\n\n`. A reset is `event: reset` + `data: ` and no `id`.
- `testkit` sits outside the layers; it may import the library, the library never imports it
  (`.importlinter` `runtime-without-extras`). Public = exported by `rdf_persistence.testkit`;
  `assert_public_imports` refuses any `rdf_persistence.testkit.<module>` import, so there is no list
  to edit, only `__all__`.
- The toolkit's own model guard scans `testkit` (`tests/unit/testkit/test_model_guard.py`,
  `LIBRARY_LAYERS`) and refuses `@dataclass` there (`FORBIDDEN_DECORATORS` in
  `rdf_persistence/testkit/guards.py`); plain records of the
  testkit are generated from `rdf_persistence/model/technical/testkit/rp_testkit.yaml` (PD-24,
  AGENTS.md principle 2; precedent `ExecResult`). See PD-1.
- In-flight `test-debt-paydown` (gated, not started) plans to move `Follow` and the route's helpers
  to `tests/events_follow.py` (its PD-8), to replace absence waits by sentinel events (its PD-3) and
  `monkeypatch` by `Relay.paused()` (its PD-2) in the same file. See RISK-1.

## Goals / Non-Goals

**Goals:** the four scenarios of `specs/rp-testkit/spec.md`; one public function (DEC-1) used by
every test that followed a stream; `Follow`, `Block`, `parsed` and `Following`'s stream plumbing
deleted; no test lost from its CI lane.

**Non-Goals:** the EPIC's no-gos (reconnect, resume helper, production client); changing the
route's behaviour; the 401/403 refusal tests, which already pass over `httpx` and stay as they are;
the `monkeypatch` of TC-37a/TC-38 (`test-debt-paydown` PD-2 owns it).

## Decisions

- **PD-1 The result records** (DEC-2 as amended 2026-11-20, OPEN-1 accepted). Two classes in `rp_testkit.yaml`, generated into
  `rdf_persistence/testkit/generated/rp_testkit.py` by `make generate`:
  - `StreamEvent` (`class_uri: rp:StreamEvent`): slots `sse_id` (alias `id`), `sse_event` (alias
    `event`), `sse_data` (alias `data`), all `string`, optional. Python reads `event.id`,
    `event.event`, `event.data`; `None` = the field was absent, `""` = present and empty.
  - `OpenedStream` (`class_uri: rp:OpenedStream`): `status` (`integer`, required), `headers` (range
    `Any`, required, a `dict[str, str]` with lower-case names), `events` (`StreamEvent`,
    multivalued, `inlined_as_list`, required). Adds the `Any` class (`class_uri: linkml:Any`) as
    `rp_access_adapters.yaml` does.
  The records are not frozen (`RpModel` validates assignment). Exported from
  `rdf_persistence.testkit`.
  Rejected: an allow-list entry in `HAND_WRITTEN` (that list is for records holding a foreign
  runtime object; a status and a dict are not).
- **PD-2 Module and export.** `rdf_persistence/testkit/streams.py` holds `open_event_stream` and
  its private parser. It is a lazy name of the testkit (`_LAZY_NAMES`, `TYPE_CHECKING` import), so
  `import rdf_persistence.testkit` does not load `api.entrypoints` (PD-3's import).
- **PD-3 Lifespan: a flag set by the toolkit's lifespan** (OPEN-2 accepted). `_run_at_startup`
  (`api/entrypoints/service.py`) sets `app.state.rp_lifespan_started = True` once start-up is done
  and `False` in its `finally`; the name is the constant `LIFESPAN_STARTED` in that module. The
  helper enters `app.router.lifespan_context(app)` for the length of the call **only when** the app
  has a `router.lifespan_context` and `getattr(app.state, LIFESPAN_STARTED, False)` is false; the
  state that lifespan yields, if a mapping, goes in the request scope's `state`. A raw ASGI callable
  (no `router`) gets no lifespan. Rejected: a `lifespan=` keyword (changes the EPIC's signature);
  detecting by probing the app (no generic signal exists; running start-up twice starts a second
  relay and event-bus consumer).
- **PD-4 One deadline.** `timeout` (seconds, > 0) bounds the head and the events together, measured
  from the call (`asyncio.timeout`). Leaving (step 7 of the algorithm) and the lifespan's shutdown are outside it.
- **PD-5 Return rules.** The call returns as soon as one holds: (a) the head arrived and `events ==
  0`; (b) `events` events arrived; (c) the response ended (`more_body` false), with the events
  parsed so far, which may be fewer than asked (a refusal, or a stream the server ended). It raises
  `TimeoutError(f"{url}: {k} of {events} events within {timeout} s")` (or `"no response head"` when
  the head did not come) otherwise. A non-event-stream response (content type not
  `text/event-stream`, e.g. a 404 problem) is read to its end and returns `events=[]`.
- **PD-6 Absence is proven by a sentinel, not a timeout** (same rule as `test-debt-paydown` PD-3):
  where a test expected `TimeoutError` to show nothing came, it now commits a visible sentinel after
  the hidden one and asserts the first event is the sentinel (the stream subscribes before it
  resumes, and its queue is FIFO).
- **PD-7 `Following` keeps its scenario role** (OPEN-3 accepted). Its `follow` method and
  `stream` attribute go; it holds `pending: asyncio.Task[OpenedStream] | None` instead, and
  `close()` cancels a pending task and runs `asyncio.gather(task, return_exceptions=True)` on its
  loop before it closes the stack and the loop.
- **PD-8 Explicit cancellation of unit-test streams.** Neither pytest-asyncio's loop teardown nor
  `ensure_future` is relied on to cancel a pending task (an unawaited task at loop close is only
  destroyed with a "Task was destroyed but it is pending" warning, and its app task would be left
  running). `test_events_route.py` gets an async fixture `streams` (function scope) yielding a
  `set[asyncio.Task]`; `opening(streams, scene, ...)` adds each task to it; teardown cancels every
  task not done and awaits `asyncio.gather(*streams, return_exceptions=True)`. The helper's own
  `finally` (algorithm step 7) then disconnects and cancels the app task, because cancelling the
  outer task raises `CancelledError` inside it. `test_streams.py` checks this: a task cancelled
  while it waits leaves its app task done.

## Algorithm / approach

`async def open_event_stream(app, url: str, *, headers: Mapping[str, str] | None = None,
events: int = 0, timeout: float = 3.0) -> OpenedStream`

1. Check `events >= 0` and `timeout > 0`, else `ValueError` naming the argument.
2. Enter the lifespan if PD-3 says so (an `AsyncExitStack`).
3. Build the scope from `urlsplit(url)`: `type http`, `asgi {"version": "3.0"}` (no
   `spec_version`, so Starlette listens for `http.disconnect`), `method GET`, `path`, `raw_path`,
   `query_string`, `headers` lower-cased with `host: test` unless given, `client`, `server`.
4. `receive`: first `http.request` (empty body, `more_body` false); then waits on a `leave` event
   and returns `http.disconnect`. `send`: `http.response.start` → status and headers (names
   decoded and lower-cased; a repeated name joined with `", "`); `http.response.body` → an
   `asyncio.Queue` of bytes, `None` when `more_body` is false.
5. Start the app as a task. Within the deadline, wait for the head or the task's end. If the task
   ended first: re-raise its exception, or `RuntimeError(f"{url}: the app sent no response")`.
6. Apply PD-5. Parsing: an incremental UTF-8 decoder (`codecs.getincrementaldecoder`); `\r\n` and
   `\r` become `\n`; blocks split on `\n\n`. In a block, a line starting with `:` is a comment and
   skipped; otherwise `name, _, value = line.partition(":")`, one leading space removed; `id`,
   `event` kept (last wins), `data` lines joined with `\n`; `retry` and unknown names ignored. A
   block with none of `id`, `event`, `data` (a keep-alive, a `: ping`) is no event.
7. `finally` (always, also on timeout or error): set `leave`; wait at most 1.0 s for the app task;
   cancel it if still running and await it, suppressing `CancelledError`; leave the lifespan.

Worked example (test TC-32 after the change):

```python
stream = asyncio.ensure_future(open_event_stream(app, events_of(settled), headers=rita, events=1))
await listening(settled.service.kit.hub)          # subscribed: the commit below is heard
await replace(settled, settled.book, settled.book_etag, "Dune Messiah")
opened = await stream                              # status 200, one StreamEvent, app task gone
```

Idempotency: the call only reads; running it twice opens two independent streams.

### Tests rewritten (DEC-1), each staying in its lane

| Test (file) | After | Lane, what it still proves |
|---|---|---|
| `test_events_route.py`, every `async with follow(...)` test (TC-32, TC-33, TC-35 x2, TC-36 x2, D-20, D-21 x3, TC-37, TC-37a, TC-37b, TC-38 x3, TC-40, default route) | test-local `opening(streams, scene, who, prefix, events=, **headers)` (PD-8) returns `asyncio.ensure_future(open_event_stream(...))`; commits run between `await listening(hub)` and `await` | unit (`test-unit-ci`), the same assertions on `OpenedStream` |
| same file: "ends" tests (TC-35 x2, TC-36 full queue) | ask for more events than come; assert `opened.events` (`[]`, or `len < 3`): PD-5 (c) | unit; the stream ends, as before |
| TC-36 resume, D-20 | a test-local `drained(hub)` (polls until every subscribed queue is empty, 3 s bound) before the next offer or the clock jump, so the first item is dequeued first | unit; "got a1 then ended", "ends after its lifetime" |
| default route, TC-37b, TC-40 (absence by `TimeoutError`) | PD-6 sentinel; TC-40's sentinel is a book posted in the other tenant | unit; nothing hidden came before the sentinel |
| TC-39, 401 | unchanged (`httpx`) | unit |
| `test_service_kit.py` TC-36 keep-alive | `SseSettings(keep_alive_seconds=0.05, max_lifetime_seconds=0.001)`; `open_event_stream(..., events=1, timeout=3.0)` returns `events == []` (the stream ends at its first wake, 0.05 s; with the 15 s default it would raise) | unit; the `sse` group reaches the route. The comment's wire form is proven by `test_streams.py` (skip) and `test_event_stream.py` (`an idle stream sends a keep-alive`) |
| `feature/test_events.py` "a hidden aggregate", "resuming a stream" | `following.pending` task started in the `Given`/`When`, awaited in the `Then`/`When`; the hidden-aggregate `Then` drops its timeout check (PD-6: the hidden replace is committed first) | feature (CI job `feature`); same scenarios |

New tests: `tests/unit/api/test_open_event_stream.py` (the four spec scenarios on the toy service,
`scene` fixture, default route) and `tests/unit/testkit/test_streams.py` (raw ASGI and plain FastAPI
apps: parsing, lifespan, leaving). Each new test gets a row in `tests/audit/scenario-map.csv`.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Keep a private ASGI reader in a test "just for one case" | express the case with the helper, PD-5/PD-6 | DEC-1; drift from the route |
| `asyncio.sleep(n)` to let the stream catch up | `listening(hub)` / `drained(hub)` | testing rule 11 |
| A `@dataclass` result | the generated records (PD-1) | the model guard, PD-24 |
| Import `rdf_persistence.testkit.streams` in a test | `from rdf_persistence.testkit import open_event_stream` | `assert_public_imports` |
| Commit before `await listening(hub)` | start the task, wait, then commit | the follower hears only what follows |
| Run the lifespan unconditionally | PD-3 | a second relay and bus consumer |
| Timing asserts (`elapsed < x`) for "returns at once" | assert it returns instead of raising (`events=1`, `timeout=0.5`) | rule 11 |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Head not sent within `timeout` | deadline | `TimeoutError` naming the URL ("no response head"); app task cancelled |
| Fewer than `events` events within `timeout` | deadline | `TimeoutError` naming the URL and `k of n` |
| Server ends the stream early (access lost, full queue, lifetime) | `more_body` false | return the events so far (PD-5 c) |
| Refusal 401/403/404 | non-event-stream content type, body ends | return status, headers, `events=[]` at once |
| App raises before the head | task done first | re-raise the app's exception |
| App returns without a head | task done, no head | `RuntimeError` naming the URL |
| App ignores `http.disconnect` | task alive 1.0 s after `leave` | cancel and await it; nothing leaks to the next test |
| Caller's test fails between starting and awaiting the task | pending task at teardown | the `streams` fixture cancels and gathers it (unit, PD-8); `Following.close()` does the same (feature, PD-7); step 7 then cancels the app task |
| Keep-alive (`: keep-alive`) or FastAPI `: ping` block | block has no `id`/`event`/`data` | skipped |
| Event split across chunks, multi-byte character split | incremental decoder, buffer until `\n\n` | parsed whole |
| `\r\n` line endings, multi-line `data` | normalisation, join with `\n` | one event |
| `events < 0`, `timeout <= 0` | argument check | `ValueError` naming the argument |
| App started by the caller vs not (PD-3) | `app.state.rp_lifespan_started` | lifespan entered only when false |
| A non-FastAPI ASGI app | no `router` attribute | no lifespan; streaming works |

## Risks / Trade-offs

- **RISK-1** (likely, medium): `test-debt-paydown` edits the same tests (its PD-2, PD-3, PD-8 and
  tasks 1.2, 1.4, 2.1) and still names `Follow`. Mitigation: this change lands first (OPEN-4
  accepted);
  its PD-6 already applies their PD-3, so their 1.4 shrinks to `test_relay.py`; their PD-8 row for
  `test_events_route` then moves only `listening`, `mount`, `replace`, `reshape_grants`,
  `with_carol`, `another_book`, `events_of`, `opening`, `drained`. The lead updates that PLAN when
  this one merges.
- **RISK-3** (low, low): `headers` typed `Any` loses static typing; the docstring and the how-to
  say it is `dict[str, str]`.
- **RISK-4** (low, medium): Starlette changes how it detects a disconnect (ASGI `spec_version`
  ≥ 2.4). Mitigation: the scope omits `spec_version`; step 7 cancels the task anyway; a
  `test_streams.py` case asserts the app task is done when the call returns.
- **RISK-5** (low, low): `drained(hub)` reads `hub._queues`, as `listening` already does. Accepted
  for the toolkit's own tests; consumers never need it.
- **Trade-off:** a one-shot call cannot hold a stream across steps; tests run it as a task. Kept,
  per DEC-1 (the class was rejected).

## Open Questions

None. OPEN-1 to OPEN-4 were answered by the owner on 2026-11-20 (inputs/qa.md): PD-1, PD-3, PD-7
and RISK-1 follow the answers.

## Delivery decisions

Taken by the lead (rule R-0007), shown to the developer at the end; the developer may overrule.

- **D-1 Scenarios signed off.** The four scenarios of `specs/rp-testkit/spec.md` were shown to the
  developer on 2026-11-20, who answered "do whatever you need to advance and continue".
- **D-2 Stacked on the planning branch.** This PLAN exists only on `docs/epics-consumer-needs`
  (`8f64ccd9`), not on `develop`. `feat/testkit-event-stream` is fast-forwarded onto it, so the
  PR carries the two planning commits until that branch merges; a rebase on `develop` after it
  merges drops them (P-0002). Resolved: the planning branch merged (#205) and the branch was
  rebased on `develop` `82ccd12c` before the PR, cleanly; `make check-generated` fresh.
- **D-3 Task order.** 1.1 and 1.2 in parallel (disjoint files), then 1.3, then 2.2, 2.3 and 3.1
  in parallel, and 2.1 last: `test_service_kit.py` and `feature/test_events.py` import `follow`,
  `parsed`, `Block` and `Follow` from `test_events_route.py`, so they drop those imports before
  2.1 deletes them.
- **D-4 Review set.** SMALL: one pass of L2 and L3 together; no checker, no adversarial tester.
- **D-6 An app that raises after the head** ends the read like any other end of the response
  (PD-5 c): the call returns the events so far and the exception is not re-raised, since the head,
  the status and the events already reached the caller. Not in the error matrix; found in 1.3.
- **D-7 The lifespan's start-up is outside the deadline**, as its shutdown already is (PD-4): the
  `timeout` bounds the head and the events only. Found in 1.3.
- **D-8 Accepted finding W1 (review, re-labelled Critical).** The rewritten TC-36 keep-alive
  test (`test_service_kit.py`) dropped `await toy.kit.relay.run_once()`; a set-up activity the
  background relay delivers after the stream subscribes ends the stream past its lifetime, so
  `events == []` holds even if the keep-alive setting never reached the route: the test can pass
  vacuously. Re-label reason: a test that cannot fail for its own claim is a spec-coverage defect.
  Fix: restore the drain before `open_event_stream`.
- **Under the floor** (review of stage 1, L2+L3; not fixed in this PR; W3 and W4 follow up in
  #214, the rest in #215):
  - W2: no test for D-6 (raise after the head) and D-7 (slow start-up); behaviour recorded, tests
    are a follow-up.
  - W3: the how-to omits D-6, D-7 and the `RuntimeError`/`ValueError` outcomes the docstring
    states; follow-up with W4's page change.
  - W4: `EventHub` has no public "a follower is subscribed" read, so a consumer cannot wait for
    the subscription before a commit without private state; a gap in our own library, filed as a
    follow-up issue (not worked around); the toolkit's own tests keep RISK-5.
  - W5: PD-2's laziness (`import rdf_persistence.testkit` loads no `api.entrypoints`) has no
    subprocess check.
  - S1: TC-37 cannot tell "replay, then live" apart from a live-only delivery.
  - S2: TC-37b's replay holds no hidden activity (pre-existing weakness).
  - S3: two sentinel checks read only the event type / compare the id with its own data.
  - S4: two concurrent calls on an app whose lifespan has not started both enter it.
  - S5: `pytest.raises(..., match=url)` treats the URL as a regex.
- **D-5 Sandbox.** The gates run with `UV_CACHE_DIR=<worktree>/temp/uv-cache` (the user cache is
  read-only in the sandbox); `temp/` is git-ignored.
