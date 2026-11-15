# Spike: FastStream 0.7.8 with Redis Streams (task 1.1, PD-4, RISK-1)

Verdict: **all four points hold (TS-1 to TS-4).** No point needs a stop. Two details differ from
the plan's wording and are marked **ADAPT** below (redelivery needs one extra option; the payload
schema needs a typed handler).

Environment: FastStream 0.7.8, redis-py 8.1.0 (pulled by `faststream[redis]==0.7.8`), Python 3.13,
Redis server 8.10.3 (`redis:8`, port 6390). Run with
`uv run --isolated --with 'faststream[redis]==0.7.8' python temp/spike_faststream/<script>.py`
(`PYTHONPATH` = the worktree, for `rdf_persistence.domain.generated.rp_provenance`: `Replace`,
`Generation`, `Invalidation`). Nothing under `rdf_persistence/`, `tests/`, `pyproject.toml` or
`uv.lock` changed. Scripts stay in `temp/spike_faststream/` (git-ignored): `ts134.py`,
`ts4_typed.py`, `ts2.py`, `ts2_fallback.py`.

## API recipe for the stage-2 adapter

```python
from faststream import AckPolicy
from faststream.redis import RedisBroker, StreamSub
from faststream.redis.annotations import RedisMessage
from faststream.specification import AsyncAPI

broker = RedisBroker(url)                      # does not connect until connect()/start()

@broker.subscriber(
    stream=StreamSub(stream, group=deployment, consumer=consumer_name,
                     polling_interval=100,     # ms
                     claim_min_idle_time=5_000),   # redelivery, see TS-2 (needs Redis 8.4+)
    ack_policy=AckPolicy.NACK_ON_ERROR,        # ack when the handler returns, no ack when it raises
)
async def handle(raw: bytes, msg: RedisMessage):   # raw: the body bytes, as published
    headers = msg.headers                       # dict[str, str]: tenant, origin, activity_class,
                                                # context + content-type, correlation_id
    await receive(Envelope(...from headers...), raw)

await broker.start()                           # connects, creates the group (XGROUP CREATE
                                               # MKSTREAM, id $ on first creation), starts polling
await broker.publish(body_json, stream=stream, headers={...})   # str body, str header values
await broker.stop()                            # close
client = broker.config.broker_config.connection.client          # redis.asyncio.Redis, after connect
spec = AsyncAPI(broker, schema_version="3.0.0").to_specification().to_jsonable()
```

Facts that matter for the adapter:

- Headers are `publish(..., headers={str: str})` and read back as `msg.headers` (a `dict`) on a
  `RedisMessage` parameter. FastStream adds `content-type` and `correlation_id`.
- A stream entry is **one field `__data__`** holding FastStream's own binary envelope (body and
  headers together), not separate Redis fields. Only FastStream consumers read it (each deployment
  of the kit does); `XRANGE` shows binary. `BinaryMessageFormatV1.parse(bytes) -> (body, headers)`
  in `faststream.redis.parser.binary` decodes it by hand (used by the fallback).
- `AckPolicy` members: `ACK_FIRST`, `ACK`, `REJECT_ON_ERROR`, `NACK_ON_ERROR`, `MANUAL`. On Redis
  every policy leaves a message that raised **pending (not acked)**, and every policy acks one that
  returned (`pending` fell to 0 after success in every run). `MANUAL` works with `await msg.ack()`.
  Recommended: `NACK_ON_ERROR` (states the intent; behaves like the rest on Redis).
- Deleting the stream (`DEL`) under a running subscriber stops it with `StreamGroupNotFoundError`
  (CRITICAL log) and `app.exit()` when run inside a `FastStream` app. Not an issue unless the
  stream is flushed; tests must create the stream before `start()`.

## TS-1: publish with four string headers; subscriber validates into `Replace`: HELD

`ts134.py` (exit 0). A `Replace` with a `Generation` and an `Invalidation` was serialised with
`model_dump_json(exclude_none=True)`, published with headers `tenant`, `origin`, `activity_class`,
`context`. The subscriber got the bytes; `Replace.model_validate_json(raw) == original`; the four
headers equal what was sent:

```
TS-1 OK headers: {'tenant': 'https://ex.org/t/1', 'origin': 'dep-a',
 'activity_class': 'https://ex.org/rp/Replace', 'context': 'https://ex.org/ctx/1'}
 all header keys: ['activity_class', 'content-type', 'context', 'correlation_id', 'origin', 'tenant']
```

Published as a `str`, FastStream marks it `text/plain` and passes `bytes` to a `raw: bytes`
handler untouched: that is what `Receive = Callable[[Envelope, bytes], ...]` (PD-6) needs.

## TS-2: group, ack after the handler returns, redelivery after a restart: HELD, with one option (ADAPT)

`ts2.py all` and `ts2.py all builtin`, `ts2_fallback.py` (all exit 0). A handler raises on
`poison`; the broker is stopped; a second broker joins the **same group and consumer name**, and a
`fresh` message is published. Results (gen2 = handled after restart; pending = XPENDING count):

| Variant | gen2 handled | pending after | Reading |
|---|---|---|---|
| default policy | `fresh` | 1 | not acked (good) but **not redelivered** |
| `REJECT_ON_ERROR` | `fresh` | 1 | same |
| `NACK_ON_ERROR` | `fresh` | 1 | same |
| `MANUAL` (`msg.ack()` on success) | `fresh` | 1 | same |
| `claim_min_idle_time=500` (`NACK_ON_ERROR`) | `poison`, `fresh` | 0 | **redelivered, then acked** |
| `claim_min_idle_time=500` (`MANUAL`) | `fresh`, `poison` | 0 | **redelivered, then acked** |
| `min_idle_time=500` (XAUTOCLAIM mode) | nothing | 0 | reads only the pending list; **new messages never arrive**: unusable alone |
| `last_id="0"` | `poison` | 0 | pending replayed, **new messages never arrive**: unusable |

So FastStream does not redeliver the pending list by itself on a restart (`read_id` is `>`), the
plan's wording "redelivered from the pending list on the next start" needs an option. Chosen
mechanism: **`StreamSub(..., claim_min_idle_time=N)`** (Redis 8.4+ `XREADGROUP ... CLAIM N`,
redis-py 7.1+; both present here). One read returns claimed pending entries first, then new ones.
Two consequences to put in the adapter and its docs:

- It also retries within a run: with `N=500` ms the `poison` was handled twice before the restart
  (the redelivery repeats every `N` ms while the handler keeps raising). Use `N` of seconds (5 to
  60 s), not milliseconds, so a failing handler is not spun hot. A restart within `N` of the
  failure sees the message only once it has been idle `N`.
- A server older than 8.4 rejects the option (FastStream raises `StreamClaimUnsupportedError` and
  stops the subscriber). The stage-2 adapter should say "Redis 8.4+" or use the fallback.

**Fallback (RISK-1), works on any Redis, shown in `ts2_fallback.py`:** before `broker.start()`,
through the broker's own client, `XAUTOCLAIM stream group consumer 0 0-0` (take over entries of a
dead consumer name), then `XREADGROUP group consumer STREAMS stream 0` (the pending history),
decode each `__data__` with `BinaryMessageFormatV1.parse`, call `receive`, `XACK`. Run output:

```
gen1 handled: [('live', 'poison')] pending: 1
drained: 1 gen2 handled: [('drain', 'poison', 't1'), ('live', 'fresh')] pending: 0
```

The fallback uses `faststream.redis.parser.binary` (not a documented public path): prefer
`claim_min_idle_time`.

## TS-3: trim by age: HELD (through the client; `publish` has no MINID) (ADAPT)

`ts134.py`. `broker.publish` takes `maxlen` only (no `minid`: `"minid" in signature` is `False`).
`XTRIM ... MINID` through the broker's redis client works: an entry published 1.5 s earlier was
removed with a 1 s age, the new one stayed:

```
TS-3 before trim: 2
TS-3 xtrim removed: 1 left: 1 ['new']
TS-3 xadd minid ok, len: 2
```

Calls: `client = broker.config.broker_config.connection.client` (a `redis.asyncio.Redis`, valid after
`connect()`/`start()`); `await client.xtrim(stream, minid=f"{now_ms - retention_ms}-0",
approximate=False)`. `approximate=True` (`~`) is cheaper and trims in whole nodes, so it may keep
a few older entries: acceptable for 7 days, wrong for a 1 s test. `await client.xadd(stream,
fields, minid=..., approximate=False)` also works, but it bypasses FastStream's envelope, so the
adapter should publish with `broker.publish` and trim with `xtrim` after each publish (RISK-1's
named fallback, now the chosen mechanism).

## TS-4: AsyncAPI document: HELD with a typed handler (ADAPT)

`ts134.py` and `ts4_typed.py` (exit 0). `AsyncAPI(broker, schema_version="3.0.0")
.to_specification().to_jsonable()` (pass the **broker**; passing the `FastStream` app fails with
`'FastStream' object has no attribute 'specification'` in 0.7.8). It names the stream and group:

```
"channels": {"rp-events-ts4:OnEvent": {"address": "rp-events-ts4",
  "bindings": {"redis": {"channel": "rp-events-ts4", "method": "xreadgroup",
                         "groupName": "g4", "consumerName": "c4"}}}}
```

With the handler typed `raw: bytes` the payload schema is only `{"format": "binary", "type":
"string"}`: no model named. With the handler typed by the model (`act: Replace`) and the publisher
setting header `content-type: application/json`, FastStream validates into `Replace` (the typed
handler got a `Replace`) and the document has `components.schemas.Replace` (plus `Generation`,
`Invalidation` with their field descriptions) and `payload: {"$ref": "#/components/schemas/Replace"}`.
Without the JSON content-type header a typed handler fails validation (`Input should be a valid
dictionary or instance of Replace`, str input). For the adapter: the runtime handler stays
`raw: bytes` (PD-6); the document is generated by the spike only (design Non-Goals), so this is
evidence, not code to keep.

## Commands run

| Command | Exit |
|---|---|
| `docker run -d --rm --name spike-redis -p 6390:6379 redis:8` | 0 |
| `uv run --isolated --with 'faststream[redis]==0.7.8' python temp/spike_faststream/inspect_api.py` | 0 (after one `__version__` fix) |
| `... ts134.py` (final run) | 0 (three earlier runs failed on script bugs: loop, DEL after start, `AsyncAPI(app)`) |
| `... ts4_typed.py` | 0 (first run failed: text/plain body; fixed with the JSON content-type header) |
| `... ts2.py all` | 0 |
| `... ts2.py all builtin` | 0 |
| `... ts2_fallback.py` | 0 (first two runs failed on the import path) |
| `docker rm -f spike-redis` | 0 |

## Upstream findings (external)

- **FastStream 0.7.8, `AsyncAPI(app)` with a `FastStream` app**: `AttributeError: 'FastStream' object
  has no attribute 'specification'`. Repro: `AsyncAPI(FastStream(RedisBroker(url)),
  schema_version="3.0.0").to_specification()`. Pass the broker instead. Possibly documented
  differently; awkward.
- **FastStream 0.7.8, no `__version__`** on the package (`faststream.__version__` raises
  `AttributeError`); use `importlib.metadata.version("faststream")`.
- **Redis binary envelope in one `__data__` field**: not a bug, but entries are unreadable to
  non-FastStream tools (`XRANGE` shows bytes). Noted for the how-to.
