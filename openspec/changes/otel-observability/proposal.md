<!-- Parents: improvements B-4 and D-3 of ../manual-revision-notes/inputs/improvements.md (analysis
     §3.3, §5.2 item 5); rule P-0010; Q-2 of ../manual-revision-notes/inputs/answers-2026-11-17.md;
     BL-5 of archive/2026-11-05-soa-python-rdf-orm (store-port tracing, planned, never built).
     Depends on: openspec/changes/technical-models (the home of generated technical schemas).
     Seeds: inputs/seed.md, which points at ../manual-revision-notes/inputs/. -->

# EPIC: Tracing and structured logging after OpenTelemetry practice

> Shaped 2026-11-17 by the leader from the developer's manual revision notes and answers; the
> developer may overrule any DEC marked "leader's choice". **Position: 3rd** of the five changes
> of the initiative, plus `ldes-view` later: after `manual-revision-notes` (which removes the
> duplicate `MessageLimitExceeded` log, A-7) and `technical-models` (which gives technical models
> their own generated schemas and places them in the layer that uses them), before
> `generator-package`.

**Golden-thread parents:** improvements B-4 and D-3, rule P-0010, the developer's note "the logging
must be aligned to best loggin practices in OpenTelmetry", and the never-built BL-5.

## Appetite

**MEDIUM.** One new capability, `rp-observability`: spans through `opentelemetry-api` at six
places, and one generated log-context model that every log call uses. About 41 log calls in 15
modules change; no behaviour of the store, the API or the events changes. Two stages.

## Why

The toolkit logs in two styles. Half its calls put identifiers into the message text, so a log
backend cannot query them; the other half use ad hoc attribute keys (`step`, `tenant`, `resource`)
that follow no convention. It has no spans at all, so an application that traces its requests sees
a FastAPI span and then nothing until the HTTP call to the store. P-0010 now asks for OpenTelemetry
practice, and the API is already installed through FastAPI.

## Solution outline

- **Spans.** The library starts spans through `opentelemetry-api` only, around: each `Store` port
  call, the commit (`Transaction.commit` in `services/session.py`), the migration runner, the start-up sweep and the live-tenant sweep, each
  relay round and each tenant database in it, and each message-bus handler and observer. Without a
  provider installed by the application they are no-ops.
- **One log context.** A `LogContext` technical model, generated from LinkML, holds every attribute
  the toolkit writes. Its fields carry OpenTelemetry semantic-convention names as aliases
  (`db.system.name`, `db.namespace`, `error.type`, `messaging.*`) and `rp.*` names for the rest
  (`rp.step`, `rp.tenant.id`, `rp.migration.name`). The same model fills log records and span
  attributes.
- **One logging style.** Every call takes a constant message, `extra=` built from a `LogContext`,
  and `exc_info=` on a failure. The caplog tests read the new attribute names.
- **Application set-up, documented.** A how-to page shows what the application installs: the SDK
  and an exporter, FastAPI's native telemetry, `opentelemetry-instrumentation-httpx`, FastStream's
  Redis telemetry middleware (passed through a new `middlewares=` argument), and the logging bridge.

```python
log.info(
    "dropping an orphan database",
    extra=log_extra(LogContext(step="drop-orphan-database", db_namespace=database, store_name=name)),
)
# a record with attributes {"rp.step": "drop-orphan-database", "db.namespace": "lib-t-x7k2",
#                           "rp.store.name": "client-a"}
```

## Key decisions

- **DEC-1** (leader's choice): target **OpenTelemetry semantic conventions v1.45.0** (released
  2026-11-02). Use stable names wherever one exists: `db.system.name`, `db.namespace`,
  `db.operation.name`, `db.response.status_code`, `error.type`, `http.response.status_code` (all
  stable). The messaging names are still in development (v1.45.0 renamed `messaging.system` to
  `messaging.system.name`); use them only where the toolkit talks to a broker (the Redis adapter
  and the kit's receive path), in their v1.45.0 spelling. Everything else goes under `rp.*`.
  Rejected: our own names for concepts the conventions name (no backend recognises them); waiting
  for messaging to be stable (it has been in development for years).
- **DEC-2** (leader's choice): **one model for log and span attributes.** `LogContext` fills both
  `extra=` and `span.set_attributes`. Reason: one name per concept, whichever signal carries it,
  and a trace and its logs correlate on the same keys. Rejected: a separate span-attribute model
  (two lists of the same names would drift).
- **DEC-3**: `LogContext` is a **technical model generated from LinkML** (the developer's Q-2), in
  the technical schemas and package that `technical-models` establishes. Its slots use LinkML
  `alias` for the dotted names, which the generator already renders (`rp_wire.py`'s `ds.name`).
  Rejected: a hand-written frozen model (the analysis's option, overruled by Q-2).
- **DEC-4**: **the library configures nothing.** It imports `opentelemetry` API modules only:
  no SDK, no exporter, no tracer or logger provider, no logging handler or level. `opentelemetry-api`
  becomes a declared dependency. Tests capture spans with `opentelemetry-sdk`'s
  `InMemorySpanExporter`, a test-group dependency (P-0008: reuse, do not build).
- **DEC-5** (leader's choice): declare **`opentelemetry-api>=1.44,<2`**, not an exact pin. Reason:
  the application's SDK must match its API version, so an exact pin would choose the consumer's
  SDK release; FastAPI 0.162 already asks for `>=1.44.0`, and the API is semver-stable. The lock
  still resolves one version (1.45.2). Rejected: the house's exact pin (PD-2 of the foundation).
- **DEC-6** (leader's choice): **store spans.** A `TracedStore` decorator in `services/store.py`,
  which the kit puts around every wired store, starts one CLIENT span per port call. Name:
  `{db.operation.name}`, the port method (`query`, `update`, `put_graph`, …); the target is omitted
  because the namespace is a tenant database and one span name per tenant would break the
  low-cardinality rule. Attributes: `db.system.name`, `db.namespace` (the dataset), and
  `db.operation.name`. Never `db.query.text`: the toolkit's SPARQL inlines literal values, which
  the conventions forbid collecting unsanitised.
- **DEC-7** (leader's choice): **internal spans** are named `rp.<area>.<action>` (for example
  `rp.session.commit`, `rp.relay.round`, `rp.bus.handle`), kind INTERNAL, with `LogContext`
  attributes. An exception that leaves a span records it, sets the status to ERROR and sets
  `error.type` to the exception's qualified class name, as the conventions ask.
- **DEC-8**: **one logging style.** A constant message (no `%` arguments, no f-string, no
  `str(error)`); attributes only through `extra=log_extra(LogContext(...))`; `rp.step` on every
  record; `exc_info=` on every failure, except where the exception's text can carry a tenant's data
  (a pydantic `ValidationError` quotes its input): there, `error.type` and `rp.error.detail` from
  `error_text`, which names fields, never values.
- **DEC-9** (leader's choice): **log or raise.** The library logs an error only where it handles
  it: it skips, sets aside, retries or swallows. Two start-up refusals keep one ERROR record before
  they raise (the IRI-policy guard and `migrate_shared`): nothing in the library logs them again,
  the process stops, and the record carries the attributes a traceback lacks.
- **DEC-10**: **BREAKING for log readers.** Attribute names change (`step` → `rp.step`,
  `tenant` → `rp.tenant.id`, …) and messages become constant. No compatibility aliases; the how-to
  page lists old and new names, and the CHANGELOG marks it.
- **DEC-11**: the application's broker telemetry needs a seam: `RedisEventBus` gains
  `middlewares=` (passed to FastStream's `RedisBroker`), so the application can add
  `RedisTelemetryMiddleware` itself. The toolkit installs none.

## Rabbit-holes

- **Order with `technical-models`.** This change needs the technical schema home and its
  generation target. If `technical-models` lands with a different folder or package name, this
  PLAN follows it; nothing else depends on the name.
- **Leaking tenant data.** Spans and log records reach a backend outside the tenant boundary.
  SPARQL text, response bodies at INFO, `ValidationError` text and activity bodies stay out
  (DEC-6, DEC-8); the existing "secret-tenant-text" tests extend to spans.
- **The Python semconv package lags the specification.** `opentelemetry-semantic-conventions`
  may not yet carry the v1.45.0 messaging spelling. It is a test-only cross-check of the stable
  names, never a runtime import.
- **The logging bridge's home moves.** Which module provides the OpenTelemetry logging handler
  changed between SDK releases; the how-to names the one in the version the lock resolves and
  says where to look.
- **Span overhead** on hot paths (one span per store call) is accepted; with no provider each span
  is a no-op object.

## No-gos

- Metrics, of any kind (counters, histograms); a later change may add them through the same API.
- Any SDK, exporter, provider, sampler, processor, logging handler, formatter or level set by the
  library or its testkit.
- The OpenTelemetry Logs API or Events API in the library: stdlib `logging` stays the only log
  path (keep.md).
- `db.query.text`, request or response bodies above DEBUG, or any tenant data in a span.
- Instrumenting HTTP routes or the httpx client ourselves: FastAPI and the httpx instrumentation
  do it.
- Spans in `domain`, or around pure functions (mapper, decoder, SPARQL builders).
- Our own copy of the semantic-convention constants as a library module.
- Changing the store, API, event or migration behaviour; changing what is logged at which level,
  beyond the merged double log of A-7 (done in `manual-revision-notes`).

---

## What Changes

- New technical group `telemetry`: `rdf_persistence/model/technical/telemetry/rp_telemetry.yaml`
  with `LogContext`, generated into `rdf_persistence/services/generated/telemetry/` (the layout of
  `technical-models` DEC-1: services and adapters use it, so it sits in `services`).
- `rdf_persistence/services/telemetry.py` (new): the tracer, `log_extra`, `traced`.
- `rdf_persistence/services/store.py`: `TracedStore`. `entrypoints/kit.py`: wraps every wired
  store in it. `adapters/fuseki.py` and `testkit/fakes.py`: a `db_system_name` class attribute.
- Spans in `services/session.py` (`Transaction.commit`), `services/migration_runner.py`, `services/sweep.py`,
  `services/tenant_sweep.py`, `services/relay.py`, `services/messagebus.py`.
- Every log call in 16 modules rewritten to DEC-8 (19 `extra=` sites, 21 interpolated calls, and
  the `problems.py` record `manual-revision-notes` adds; design PD-6);
  `adapters/redis_events.py` renames its `logger` to `log`.
- `adapters/redis_events.py`: `RedisEventBus(middlewares=)`.
- `pyproject.toml`: `opentelemetry-api>=1.44,<2` in `dependencies`; `opentelemetry-sdk` in the
  `test` group. `ruff.toml`: `opentelemetry.sdk` banned in the package (TID251).
- Tests: the caplog tests (about 20 test modules) read the new names; new unit tests for the model,
  the helpers and each span site; a feature file.
- Docs: a new how-to `howto/observability.adoc`, its `questions.adoc` entry and nav line, a step
  in `howto/adopt.adoc`. **BREAKING** for whoever queries the old log attributes (DEC-10).

## Capabilities

### New Capabilities

- `rp-observability`: the spans the toolkit starts, the attributes of its spans and log records,
  the logging style, and what the library leaves to the application.

### Modified Capabilities

None.

## Impact

- A consumer gets spans and structured logs for free once it installs an SDK and a logging bridge;
  without them nothing changes but the log message texts and attribute names (DEC-10).
- A consumer's own `Store` works unchanged; it may add `db_system_name` to name its product.
- `RedisEventBus` gains an optional argument; existing calls are unchanged.
- One new declared runtime dependency, already installed transitively.

---

## As built

Reconciled 2026-11-17 by the lead, before PR 2 merged (P-0004). Decisions taken during delivery
are `D-1` to `D-9` in [design.md](design.md#delivery-decisions).

| Promised | Delivered | PR |
|---|---|---|
| `LogContext` generated from LinkML in the `telemetry` group | 28 slots as shaped, a 29th (`exception.type`) by D-10; `services/generated/telemetry/` | #149 |
| Every log call in the DEC-8 style | 41 calls in 16 modules (the shape said 15; the `problems.py` record of `manual-revision-notes` is the 16th); a guard test over the package that also requires `extra=` on every call (D-6) | #149, PR 2 |
| Spans at the six places of B-4 | Store port (`TracedStore`), commit, migrations, both sweeps, relay round and database, bus handler and observer, as PD-5 | PR 2 |
| `opentelemetry-api>=1.44,<2`; SDK test-only, banned in the package | As shaped | PR 2 |
| `RedisEventBus(middlewares=)` | As shaped | PR 2 |
| How-to "See what the toolkit is doing" | As shaped, cold-read and revised | PR 2 |

**What differs from the shape, and why:**

- **The generator changed** (D-4). The shape assumed a dotted alias already renders; linkml names
  the field after the alias (`rp.step` → `rp_step`). Our pydantic generator now names a field after
  its slot when the alias is no Python name. Side effect, BREAKING for a consumer that read it:
  `FusekiDataset.ds_name` is now `fuseki_dataset_name`.
- **mypy reads field names** (D-5): the `pydantic.mypy` plugin is enabled for the package.
- **The logging bridge** (D-9): the SDK's own `LoggingHandler` is deprecated in 1.45.2; the how-to
  names `opentelemetry-instrumentation-logging`'s. FastAPI's native telemetry logs exception
  messages by default; RISK-3's residual and the how-to say so.
- **Order** (D-1, D-8): delivered while `technical-models` stages 3–4 were in flight; nothing in
  this change waited for them.

- **No exception text in a span** (D-10, from the full review): `traced` records an exception's
  type only, never its message or traceback; the 500 record drops `exc_info` where a stored
  value could be quoted (D-11).

Nothing the shape promised was dropped. The spec delta `rp-observability` is true of the code: each
scenario is a feature test in `tests/feature/observability.feature`, except "no provider
installed" (TC-14, which shows a span is a no-op without a provider; no test commits without
one), "the package loads no SDK" (TC-17) and "a traced event" (TC-28, container), which the
feature file names. "A commit's store call" runs on the fake store (`rdflib`); its Fuseki spelling
is covered by TC-26 (`system_name_of` gives `fuseki`) and TC-27 (the kit wraps every store), not by
a container span (D-12).
