> Derives from: EPIC `otel-observability` ([proposal.md](proposal.md)), new capability
> `rp-observability`. Depends on `technical-models` (the technical schema home). Type: Implementation.

## Context

Read on `docs/manual-revision-notes` (48f80c6):

- **Loggers.** 15 modules hold a module logger, `log`, except `logger` in
  `adapters/redis_events.py:25`. No handler, level or formatter is set anywhere; `print` only in the
  CLI. This stays (keep.md).
- **41 log calls.** 19 pass `extra=` with ad hoc keys: `iri_policy_guard.py:63,86`,
  `tenant_sweep.py:202,213`, `sweep.py:57,64,85,113,119`, `tenancy.py:589,940`,
  `tenant_dump.py:114,120,245`, `migration_runner.py:67,98,240`, `file_removal.py:55,61`. The
  other 22 interpolate identifiers into the message: `kit.py:229,231,241,260,269,275,279`,
  `relay.py:119,152,154,161,202`, `messagebus.py:141,150,198`, `session.py:1509,1553`,
  `fuseki.py:56`, `zitadel.py:147`, `s3.py:57`, `redis_events.py:63,85`, `tenancy.py:584`
  (interpolated and `extra=` at once). Lines are the line of the call (`tenant_dump.py:112,120,243`,
  `migration_runner.py:238`, `file_removal.py:53,59`, `sweep.py:55,62,83,111,118`,
  `tenant_sweep.py:200,211` where the list above names the `extra=` line).
- **What `manual-revision-notes` changes first** (its PD-9, A-7): `messagebus.py:150` goes, and
  `entrypoints/problems.py` gains one ERROR call, `"internal error answered"`, for a mapped error
  answered as 500, with a bare `extra=` dict whose `error.type` is already the qualified class
  name (its PD-9, reconciled 2026-11-17). So this change starts from **41 calls in 16 modules**
  (40 above plus that one), and that call breaks DEC-8 and PD-9 as it lands (no `rp.step`, no
  `log_extra`); PD-6 rewrites it.
- **`tenancy.py:940`** (`_log_step`) passes its `step` argument as the message: a variable message,
  which PD-9 refuses. **`s3.py:57`** logs only a code the adapter does not map: `NoSuchBucket`,
  `NoSuchKey` and the bucket-exists codes return before it.
- **The relay task** is created in the lifespan of `entrypoints/service.py:174`, after the start-up
  calls; it copies the lifespan's context, so a span current there (an application's or an
  instrumentation's) would parent every round.
- **Pre-formatted messages:** `iri_policy_guard.py:62` (f-string), `migration_runner.py:67,98`
  (`str(error)`). `migration_runner._failure` (`:155`) returns the `dict[str, str]` the analysis
  lists (§5.2 item 4); this change replaces it with a `LogContext`.
- **Keys in use:** `step`, `tenant`, `resource`, `database`, `schema`, `migration`, `cause`,
  `fields`, `store`, `recorded_store`, `found_store`, `blobs`, `source`, `system_created`,
  `resources`.
- **Tests reading them:** `getattr(r, "step")`, `r.step`, `r.__dict__["…"]` in
  `test_migration_runner.py:351-392,506`, `test_migration_runner_adversarial.py:556`,
  `test_tenant_dump.py:698,735-742,996`, `test_tenant_sweep.py:557,563`, `test_sweep.py:305`,
  `test_iri_policy_guard.py:121`, `test_tenancy.py:428`, `test_tenancy_stores.py:361,375`,
  `test_remove_with_files.py:90,96`, `test_tenant_stores_adversarial.py:252`. Message text in
  `caplog.text` or `getMessage()`: `test_zitadel.py:388-389`, `test_fuseki_store.py:243`,
  `test_receive.py:162-163`, `test_relay_adversarial.py:270-271`, `test_session_activity.py:332-334`,
  `test_session_activity_adversarial.py:275,669`, `test_sweep.py:125,138,262`,
  `test_messagebus.py:182,277,448`, `test_messagebus_adversarial.py:573-775`,
  `tests/feature/test_messages.py:550`.
- **No spans anywhere.** `opentelemetry-api` 1.45.2 is in `uv.lock` through FastAPI 0.162
  (`Requires-Dist: opentelemetry-api>=1.44.0`); `opentelemetry-sdk` is not installed.
- **The commit** the EPIC calls `Session.commit` is `Transaction.commit` (`session.py:1440`); the
  mapper's `UnitOfWork.commit` (`mapper.py:399`) calls it once, or once per batch.
- **FastAPI 0.162** has native telemetry (`FastAPI(telemetry=TelemetryConfig)`, on by default,
  using the global providers). The consumer builds the `FastAPI` app and passes it to
  `install_service`, so the toolkit never touches it.
- **FastStream 0.7.8** has `faststream.redis.opentelemetry.RedisTelemetryMiddleware`; it needs
  `opentelemetry.semconv` (shipped with the SDK). `RedisEventBus.start` builds its `RedisBroker`
  itself (`redis_events.py:67`) with no way to pass middlewares.
- **Dotted aliases already generate:** `rp_wire.py:349` has `Field(alias="ds.name")`; `RpModel`
  sets `serialize_by_alias` and `validate_by_name` (`domain/base.py`).
- **Semantic conventions** v1.45.0 (2026-11-02) is the latest release. Database spans are stable,
  with `db.system.name`, `db.namespace`, `db.operation.name`, `db.response.status_code`,
  `error.type` stable; no well-known `db.system.name` value covers a SPARQL store, so a custom
  lowercase product name is used. Span name rule: `{db.operation.name} {target}`, the target
  omitted when not available. `db.query.text` without sanitisation SHOULD NOT be collected.
  Messaging stays in development; v1.45.0 renamed `messaging.system` to `messaging.system.name`.

## Goals / Non-Goals

**Goals:**

- Spans at the six places of B-4, no-ops without a provider (DEC-4, DEC-6, DEC-7).
- One generated `LogContext`; every log call in the package in the DEC-8 style.
- A guard that keeps the style: a test fails on a log call that breaks it.
- The application-side set-up on one how-to page, including the old-to-new attribute table.

**Non-Goals:** the EPIC's No-gos. Also: changing any log level, or adding log calls where none
exist today (beyond none at all: this change adds no new record).

## Decisions

Settled in the EPIC and cited: DEC-1 to DEC-11. New:

- **PD-1 The schema.** A sixth technical group, `telemetry`, as `technical-models` DEC-2 foresees:
  `rdf_persistence/model/technical/telemetry/rp_telemetry.yaml` (annotation `module_kind:
  technical`), generated into `rdf_persistence/services/generated/telemetry/` (the lowest layer
  every user may import, `technical-models` DEC-1: services and adapters log with it) by its own
  `[[tool.rp-generate]]` target with `kind = "technical"` and `openapi = false`. One class
  `LogContext`, every slot optional but `step`, each slot with `alias` set to its attribute name.
  If `technical-models` lands with other paths, these follow it; nothing else in this PLAN depends
  on them. Adapters and services import it; `domain` does not (technical-models DEC-3).
- **PD-2 The slots** (Python name → attribute, range, status in v1.45.0):

  | Slot | Attribute | Range | Status |
  |---|---|---|---|
  | `step` (required) | `rp.step` | string | rp |
  | `tenant_id` | `rp.tenant.id` | string | rp |
  | `resource` | `rp.resource` | string | rp |
  | `store_name` | `rp.store.name` | string | rp |
  | `found_store_name` | `rp.store.found_name` | string | rp |
  | `schema_id` | `rp.schema.id` | string | rp |
  | `migration_name` | `rp.migration.name` | string | rp |
  | `blob_count` | `rp.blob.count` | integer | rp |
  | `source_tenant_id` | `rp.restore.source_tenant.id` | string | rp |
  | `policy_fields` | `rp.iri_policy.fields` | string, multivalued | rp |
  | `system_created` | `rp.sweep.system_created` | boolean | rp |
  | `resources` | `rp.sweep.resources` | string, multivalued | rp |
  | `activity_id` | `rp.activity.id` | string | rp |
  | `activity_class` | `rp.activity.class` | string (the Python class name) | rp |
  | `activity_class_iri` | `rp.activity.class_iri` | string (the class IRI an envelope carries) | rp |
  | `event_origin` | `rp.event.origin` | string (the publishing deployment) | rp |
  | `observer_name` | `rp.observer.name` | string | rp |
  | `message_limit` | `rp.message.limit` | integer | rp |
  | `error_detail` | `rp.error.detail` | string | rp |
  | `response_body` | `rp.store.response_body` | string | rp (DEBUG only) |
  | `db_system_name` | `db.system.name` | string | stable |
  | `db_namespace` | `db.namespace` | string | stable |
  | `db_operation_name` | `db.operation.name` | string | stable |
  | `db_response_status_code` | `db.response.status_code` | string | stable |
  | `error_type` | `error.type` | string | stable |
  | `http_response_status_code` | `http.response.status_code` | integer | stable |
  | `messaging_system_name` | `messaging.system.name` | string | development |
  | `messaging_destination_name` | `messaging.destination.name` | string | development |

  28 slots. Every range is one OpenTelemetry attribute value type (string, int, bool, or a list of
  one). `cause` goes: the exception travels in `exc_info` (DEC-8). Each slot is written by at least
  one row of PD-6 or PD-5; a slot no site writes is not added (`messaging.message.id` is left out:
  the kit's `receive` never sees the broker's message id).
- **PD-3 The helpers**, `rdf_persistence/services/telemetry.py` (new; hand-written, it is
  behaviour, not data):
  - `log_extra(context: LogContext) -> dict[str, object]`:
    `context.model_dump(by_alias=True, exclude_none=True)` (`by_alias` explicit, so it does not
    rest on the base class's `serialize_by_alias`). The dict is the `logging` boundary (P-0007).
  - `error_type(error: BaseException) -> str`: `f"{type(error).__module__}.{type(error).__qualname__}"`,
    the one spelling of `error.type` for an exception, in spans and records alike (DEC-7). A
    non-exception error (an S3 code) is written as it comes.
  - `tracer = trace.get_tracer("rdf_persistence", version("rdf-persistence"))` at import, with
    `importlib.metadata.version` (not `rdf_persistence.__version__`, which would import the package
    root from a services module); the API returns a proxy that follows a provider installed later.
  - `traced(name: str, context: LogContext, *, kind=SpanKind.INTERNAL, root: bool = False)`: a
    context manager over `tracer.start_as_current_span(name, kind=kind,
    attributes=log_extra(context), context=Context() if root else None)`, whose own defaults record
    the exception and set the ERROR status; `traced` adds `error.type` (`error_type`) and re-raises.
    `root=True` starts a new trace whatever span is current (PD-5, the relay round). A decorator
    form is not offered: each site builds its context from its arguments.
  - The module joins the `nothing-in-services-imports-the-bus` list in `.importlinter`.
- **PD-4 Store spans** (DEC-6). `TracedStore(store, system_name)` in `services/store.py`, each port
  method inside `traced(method_name, LogContext(step=method_name, db_system_name=…,
  db_namespace=dataset, db_operation_name=method_name), kind=SpanKind.CLIENT)`; `list_datasets`
  has no namespace. The kit builds `ToolkitStore(TracedStore(raw, system_name_of(raw)))` once per
  raw store, keeping the identity keying of tenant-stores PD-16. `system_name_of` reads an optional
  class attribute `db_system_name` and falls back to `"sparql"`. `FusekiStore.db_system_name =
  "fuseki"`; `FakeStore.db_system_name = "rdflib"`. The `Store` protocol is unchanged.
- **PD-5 Internal spans** (DEC-7):

  | Span | Where | Attributes |
  |---|---|---|
  | `rp.session.commit` | `Transaction.commit`, only when there are roots (after the early return) | `rp.step=commit`, `db.namespace` |
  | `rp.migration.shared` / `rp.migration.tenants` | `migrate_shared` / `migrate_tenants` | `rp.step=migrate-shared` / `migrate-tenants` |
  | `rp.migration.database` | `migrate_database` | `rp.step=migrate-database`, `db.namespace` |
  | `rp.migration.apply` | `_apply` | `rp.step=migrate`, `db.namespace`, `rp.schema.id`, `rp.migration.name` |
  | `rp.sweep` | `sweep` | `rp.step=sweep` |
  | `rp.tenant_sweep` | `sweep_tenant` | `rp.step=tenant-sweep`, `rp.tenant.id` |
  | `rp.relay.round` | `Relay.run_once`, inside the lock, `root=True` | `rp.step=relay-round` |
  | `rp.relay.database` | `Relay._relay_database`, inside its `try` | `rp.step=relay-database`, `rp.tenant.id` |
  | `rp.bus.handle` | `MessageBus._start`, around `await handler(command, work)` only | `rp.step=bus-handle`, `rp.activity.class`, `rp.activity.id` |
  | `rp.bus.observe` | `MessageBus.publish`, around `await observer(...)`, inside its `try` | `rp.step=bus-observe`, `rp.observer.name` (`_name(observer)`), `rp.activity.class`, `rp.activity.id` |

  `rp.activity.class` is `type(activity).__name__`; `rp.activity.id` is `activity.id`, left out
  when `None`. Placement rule: where the site swallows a failure (a skipped relay database, a
  failed observer), the span opens **inside** the `try`, so the exception leaves the span first and
  marks it ERROR, and the parent stays UNSET. `DatabaseGone` marks its `rp.relay.database` ERROR
  too; accepted (the database did fail this round). The round is a root span (`root=True`): the
  relay task inherits the lifespan's context (design Context), and a round must not join a trace
  that never ends.
- **PD-6 The log calls.** Each of the 41 calls keeps its level and takes the message and context
  of this table (the single source; tasks cite it). `exc` is the caught exception; `err` is
  `error_type(exc)`; "as today" keeps the call's present `exc_info`. Slot names are PD-2's Python
  names.

  | Call | Message (constant) | `step` and other slots | `exc_info` |
  |---|---|---|---|
  | `iri_policy_guard.py:63` | `the IRI policy cannot change once there is data` | `iri-policy`; `policy_fields` | none (the raise follows) |
  | `iri_policy_guard.py:86` | `the recorded IRI policy is unreadable` | `iri-policy`; `error_detail=why` | none |
  | `sweep.py:55` | (unchanged) | `skip-sweep`; `system_created`, `resources` | none |
  | `sweep.py:62` | (unchanged) | `finish-deletion`; `tenant_id` | none |
  | `sweep.py:83` | (unchanged) | `misplaced-tenant`; `tenant_id`, `store_name` (recorded), `found_store_name` | none |
  | `sweep.py:111` | (unchanged) | `drop-orphan-database`; `db_namespace`, `store_name` | none |
  | `sweep.py:118` | (unchanged) | `drop-orphan-bucket`; `resource` | none |
  | `tenancy.py:584` | `a failed step could not drop what it made; left to the sweep` | the caller's `step`; `tenant_id`, `resource` | as today |
  | `tenancy.py:940` (`_log_step`) | `changed a resource of a tenant` | the caller's `step`; `tenant_id`, `resource` | none |
  | `tenant_dump.py:112` | (unchanged) | `dump-blob-gone`; `tenant_id`, `resource` | none |
  | `tenant_dump.py:120` | `dumped a tenant` | `dump`; `tenant_id`, `blob_count` | none |
  | `tenant_dump.py:243` | `restored a tenant` | `restore`; `tenant_id`, `source_tenant_id` | none |
  | `migration_runner.py:67` | `a shared database could not be migrated` | `migrate-shared`; `db_namespace`, `schema_id`, `migration_name` | `exc` |
  | `migration_runner.py:98` | `a tenant could not be migrated; set aside` | `migrate-tenant`; `tenant_id`, `schema_id`, `migration_name` | `exc` |
  | `migration_runner.py:238` | (unchanged) | `migrate`; `db_namespace`, `schema_id`, `migration_name` | none |
  | `file_removal.py:53` | (unchanged) | `remove-blob-failed`; `tenant_id`, `resource` | as today |
  | `file_removal.py:59` | (unchanged) | `remove-blob`; `tenant_id`, `resource` | none |
  | `tenant_sweep.py:200` | (unchanged) | `sweep-blob-skipped`; `tenant_id`, `resource` | none |
  | `tenant_sweep.py:211` (`_log_removal`) | (unchanged) | the caller's `step`; `tenant_id`, `resource` | none |
  | `kit.py:229` | `skipped an event this deployment published` | `receive-own-event`; `activity_class_iri` | none |
  | `kit.py:231` | `skipped an event: the kit has no message bus` | `receive-no-bus`; `activity_class_iri` | none |
  | `kit.py:241` | `skipped an event whose class is unknown or whose body is invalid` | `receive-invalid-event`; `activity_class_iri`, `event_origin`, `error_type=err`, `error_detail=error_text(exc)` | none (PD-8) |
  | `kit.py:260` | `skipped an event whose tenant has no session here` | `receive-no-session`; `activity_id`, `tenant_id`, `error_type=err` | `exc` |
  | `kit.py:269` | `skipped an event whose tenant is no IRI` | `receive-invalid-tenant`; `activity_id`, `tenant_id`, `error_type=err` | `exc` |
  | `kit.py:275` | `skipped an event of a tenant this deployment lacks` | `receive-unknown-tenant`; `activity_id`, `tenant_id`, `error_type=err` | `exc` |
  | `kit.py:279` | `an incoming event exceeded the message limit` | `receive-message-limit`; `activity_id`, `message_limit=exc.limit`, `error_type=err` | `exc` |
  | `relay.py:119` | (unchanged) | `relay-round-failed` | as today |
  | `relay.py:152` | `the database of a tenant is gone; skipped this round` | `relay-database-gone`; `tenant_id` | none |
  | `relay.py:154` | `the relay failed on the database of a tenant; skipped this round` | `relay-database-failed`; `tenant_id` | as today |
  | `relay.py:161` | `a pending activity cannot be decoded; marked failed` | `relay-undecodable`; `activity_id=iri`, `error_type=err`, `error_detail=error_text(exc)` | as today (`None` for a `ValidationError`, PD-8) |
  | `relay.py:202` | `publishing an activity failed; retried next round` | `relay-publish-failed`; `activity_id`, `tenant_id` | as today |
  | `messagebus.py:141` | `a queued command failed` | `bus-queued-failed`; `activity_class`, `activity_id` | as today |
  | `messagebus.py:198` | `an observer failed` | `bus-observer-failed`; `observer_name`, `activity_class`, `activity_id` | as today |
  | `session.py:1509` | `an activity was applied but overtaken; not handed to on_commit` | `commit-overtaken`; `activity_id` | none |
  | `session.py:1553` | `on_commit failed` | `commit-hook-failed`; `activity_id` | as today |
  | `fuseki.py:56` | `Fuseki refused a request with 400` | `store-bad-request`; `db_system_name="fuseki"`, `db_response_status_code="400"`, `response_body` | none (DEBUG) |
  | `zitadel.py:147` | `the identity provider answered an error` | `identity-error`; `http_response_status_code` | none |
  | `s3.py:57` | `the object store refused a request` | `file-store-refused`; `error_type=code or str(status)` | none |
  | `redis_events.py:63` | `trimming the stream failed; the entry was published` | `event-trim-failed`; `messaging_system_name="redis"`, `messaging_destination_name` | as today |
  | `redis_events.py:85` | `dropped a message with an invalid envelope` | `event-invalid-envelope`; `messaging_system_name="redis"`, `messaging_destination_name` | none |
  | `problems.py` (added by `manual-revision-notes`) | `internal error answered` (kept) | `answer-internal-error`; `error_type=err` (the same qualified name, now through `error_type`) | `exc` (kept) |

  Old key → new attribute (the how-to's table, DEC-10): `step` → `rp.step`; `tenant` →
  `rp.tenant.id`; `resource` → `rp.resource` (`db.namespace` at `sweep.py:111`); `database` →
  `db.namespace`; `schema` → `rp.schema.id`; `migration` → `rp.migration.name`; `cause` → the
  record's exception (`exc_info`); `fields` → `rp.iri_policy.fields`; `store` and `recorded_store`
  → `rp.store.name`; `found_store` → `rp.store.found_name`; `blobs` → `rp.blob.count`; `source` →
  `rp.restore.source_tenant.id`; `system_created` → `rp.sweep.system_created`; `resources` →
  `rp.sweep.resources`; `error.type` (from `problems.py`) keeps its name and its qualified value.

  `migration_runner._failure` is deleted. `_log_step` and `_log_removal` keep their role and build
  the `LogContext`; their message is the constant above, the step a slot.
- **PD-7 Log or raise** (DEC-9). `messagebus.py:150` was removed by A-7 in `manual-revision-notes`;
  if it is still there when this change starts, task 1.3 removes it under A-7's id. The kit's
  `receive` keeps the single ERROR record. `iri_policy_guard` and `migrate_shared` keep theirs.
  The 500 record `problems.py` gains in `manual-revision-notes` is the handler's own and stays;
  only its `extra=` changes (PD-6's last row); `error.type` is already qualified.
- **PD-8 Tenant data stays out** (DEC-8). Decoding failures (`kit.py:241`, `relay.py:161`) log
  `error.type` and `rp.error.detail=error_text(error)`, with no `exc_info`, as today's text does.
  Fuseki's 400 body stays at DEBUG, now as `rp.store.response_body`. Zitadel's status only, never
  its body (`test_zitadel.py:389`).
- **PD-9 The guard.** `tests/unit/test_log_calls.py` walks the package's AST (generated code
  excluded): every call `log.<level>(…)` has exactly one positional argument, a string literal; every call
  passes `extra=` as a call of `log_extra`; any module-level logger is `log = logging.getLogger(__name__)`.
  Reuse: the stdlib `ast` module; no new tool.
- **PD-10 Test capture.** `opentelemetry-sdk` (same release as the API in the lock) in the `test`
  group. `tests/conftest.py` gains a session fixture that installs one `TracerProvider` with a
  `SimpleSpanProcessor(InMemorySpanExporter())` (the global provider can be set once per process,
  and each xdist worker is one process), and a function fixture `spans` that clears the exporter
  and yields a callable `() -> tuple[ReadableSpan, ...]` over the exporter's finished spans (the
  test calls it after the code under test runs). Tests that do not request `spans` still record
  into the exporter once the provider is set; the next `spans` request clears it. A test helper `tests/logs.py` gives `attributes(record)` (the
  dotted attributes of a `LogRecord`) and `records_of(caplog, step)`. Neither goes in the testkit
  (DEC-4: the testkit configures nothing either).
- **PD-11 The SDK stays out.** `ruff.toml` bans `opentelemetry.sdk` under TID251 (tests are
  already exempt from TID251); import-linter cannot forbid a submodule of an external package.
  `tests/unit/test_packaging.py` gains a subprocess check that importing `rdf_persistence` and its
  kit loads no `opentelemetry.sdk` module.
- **PD-12 Cross-check of names.** A unit test compares each stable attribute of PD-2 with the
  constant in `opentelemetry.semconv.attributes` (installed with the SDK, test only). The
  development names are compared with the PD-2 table, pinned to v1.45.0, so a rename is a
  deliberate edit.
- **PD-13 Broker seam** (DEC-11). `RedisEventBus(..., middlewares: Sequence[BrokerMiddleware] = ())`
  passed to `RedisBroker(self._url, middlewares=…)`. The envelope stays in the message headers;
  the middleware adds `traceparent` beside it, which `handle` ignores (it reads only
  `ENVELOPE_FIELDS`).

## Algorithm / approach

Worked example: an application installs an SDK, the logging bridge and the httpx instrumentation,
then a request `PUT /t/x7k2/books/b1` arrives.

1. FastAPI's native telemetry opens the SERVER span `PUT /t/{tenant}/books/{id}`.
2. The route's commit opens `rp.session.commit` (`db.namespace=lib-t-x7k2`).
3. Inside it, `TracedStore` opens CLIENT `update` (`db.system.name=fuseki`,
   `db.namespace=lib-t-x7k2`, `db.operation.name=update`); the httpx instrumentation opens its HTTP
   CLIENT span beneath it.
4. The commit hands the activity to the bus: `rp.bus.observe` per observer, under the same trace.
5. Later the relay's background task opens `rp.relay.round` (a new trace), `rp.relay.database`
   per tenant, `query` spans, and FastStream's PRODUCER span for each publish. Another deployment's
   FastStream CONSUMER span continues that trace through `traceparent`.
6. A sweep log record during start-up: `log.info("dropping an orphan database",
   extra=log_extra(LogContext(step="drop-orphan-database", db_namespace="lib-t-zzzz",
   store_name="client-a")))`. The bridge turns it into a log record with body `dropping an orphan
   database`, attributes `rp.step`, `db.namespace`, `rp.store.name`, and the current trace and span
   ids.

Without an SDK: steps 1 to 5 produce no-op spans; the record of step 6 reaches whatever handler
the application set, with the attributes on the `LogRecord`.

Idempotency: spans and log records are side effects outside the data; a retried operation makes a
new span, which is what it should show. No operation changes its result.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| `log.info("dropped %s", name)` or an f-string message | constant message, `db_namespace=name` in the context | A backend groups and queries by message and attributes (DEC-8) |
| `extra={"step": …}` with bare keys | `extra=log_extra(LogContext(...))` | One concept, one generated model (P-0007, DEC-3) |
| `log.error(str(error))` | a constant message and `exc_info=error` | The bridge maps the exception to `exception.*` |
| `exc_info` on a `ValidationError` from tenant data | `error_type` and `error_detail=error_text(error)` | Its text quotes the input (PD-8) |
| Set `db.query.text`, or a body above DEBUG | Leave it out | Unsanitised SPARQL inlines values (DEC-6) |
| `trace.set_tracer_provider`, `LoggingHandler`, `basicConfig` in the package or testkit | The application does it; tests use the conftest fixture | DEC-4 |
| A span name carrying a tenant or IRI | The fixed name; identifiers as attributes | Low cardinality (DEC-6, DEC-7) |
| Log, then raise, then log again above | Log where it is handled | DEC-9 |
| A hand-written constant `"db.namespace"` in a module | The alias on the generated slot | LinkML is the single source (DEC-3) |
| Assert on `caplog.text` for an identifier | `attributes(record)["rp.activity.id"]` | Identifiers left the message |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| No tracer provider installed | The API returns no-op spans | Nothing recorded; behaviour unchanged (TC-14) |
| A port call raises (`StoreUnavailable`, `NotFound`, `BadQuery`) | Exception leaves `traced` | Span status ERROR, exception event, `error.type` the qualified class name; the exception propagates unchanged (TC-16) |
| An exception swallowed by its caller (`suppress(NotFound)` in the sweep) | As above, inside the inner span | That span is ERROR; the parent is not. Accepted: the store call did fail |
| A swallowed relay or observer failure | `except` after the span closed | The child span ERROR, one WARNING/ERROR record with `exc_info` (as today) |
| A `LogContext` built with a wrong type or unknown field | pydantic `ValidationError` at the log call | The test of that call fails; `RpModel` forbids extra fields (`extra="forbid"`) |
| A `LogContext` without `step` | `ValidationError` | As above; the guard test makes every call build one |
| An attribute key clashing with a `LogRecord` field | `logging` raises `KeyError` on `extra` | Impossible by construction: every key is dotted (TC-04) |
| A consumer's `Store` without `db_system_name` | `system_name_of` fallback | `db.system.name=sparql` (TC-26) |
| The application's SDK of another release than the lock's API | pip/uv resolution on the consumer side | Allowed by the range (DEC-5) |
| A decoding failure carries tenant text | `error_text` drops values | No tenant text in records or spans (TC-11, TC-18) |
| A semconv rename of a development name | The cross-check table (PD-12) on the next bump | A deliberate edit of PD-2 and the schema, noted as BREAKING |
| The relay task started under a current span (an application's lifespan instrumentation) | `root=True` on `rp.relay.round` | Each round is a new trace; TC-34 asserts the round has no parent |
| A log call added on `develop` after this PLAN was read (as `problems.py` was) | TC-23, the guard over the whole package | The guard fails naming the file and line; the task that meets it rewrites the call to PD-6's style |
| `manual-revision-notes` not yet merged when stage 1 starts | `messagebus.py:150` still there; `problems.py` without a log call | Stage 1 waits for it (it is first in the order); PD-7's fallback removes `:150` under A-7's id if it must |

## Risks / Trade-offs

- **RISK-1 Log readers break** (DEC-10). Likelihood high for anyone who queries the old keys or
  message texts (a consumer's dashboards or alerts), impact low to medium (a query returns nothing
  until fixed). Mitigation: the how-to's old-to-new table, a BREAKING line in the CHANGELOG, and
  the consumer's change names this change (D-12).
- **RISK-2 Messaging names change again.** Likelihood medium (still in development), impact low:
  three attributes at two sites. Mitigation: confined by DEC-1, pinned and cross-checked (PD-12).
  Accepted.
- **RISK-3 Tenant data reaches a telemetry backend.** Likelihood low after PD-8, impact high (data
  leaves the tenant boundary). Mitigation: no query text, no bodies above DEBUG, `error_text` for
  validation errors, TC-11 and TC-18 with a secret marker in logs and spans. Residual: an
  exception message a consumer's validator writes with data in it reaches `exc_info`; the how-to
  says so.
- **RISK-4 `technical-models` changes shape.** Likelihood medium (it is shaped in parallel),
  impact low: only the schema path and package name move (PD-1). If it is delayed, this change
  waits; it is third in the order.
- **RISK-5 Span volume.** With a provider and no sampling, a listing of many aggregates makes one
  span per store call. Likelihood medium in a busy service, impact cost only. Accepted; the how-to
  points at the SDK's samplers.
- **RISK-6 The global provider in tests.** One provider per process means a test that wants its
  own provider cannot have it. Accepted: the `spans` fixture clears between tests, and nothing in
  the suite needs a second provider.
- **RISK-7 Two spellings of `error.type` across the initiative.** Closed in the cross-change
  reconciliation of 2026-11-17: `manual-revision-notes` PD-9 writes the qualified class name as
  DEC-7 does, so the attribute never changes value between the two merges; TC-13c checks it.
- **RISK-8 A relay round joins a never-ending trace.** Likelihood medium (any lifespan span), impact
  medium (one giant trace, rounds invisible as their own). Mitigation: `root=True` (PD-3, PD-5).
- **Trade-off:** span names without the database (DEC-6) mean a trace view shows `query` rather
  than `query lib-t-x7k2`; the namespace is one click away as an attribute.

## Open Questions

None blocking. Leader's choices the developer may overrule: DEC-1, DEC-2, DEC-5, DEC-6, DEC-7,
DEC-9, and PD-4's fallback `"sparql"`.

## Delivery decisions

- **D-1 Start before `technical-models` ends** (developer, 2026-11-17; deviation from the PLAN's
  order). Stage 1 starts while `technical-models` stages 3–4 are in flight in another session.
  What this change needs from it has landed: PR #144 (the `technical` target kind, DEC-2's groups),
  PR #145 (stage 2); `manual-revision-notes` A-7 is merged (`messagebus.py:150` gone,
  `problems.py:202` carries the `internal error answered` record). **RISK-4 checked against
  `develop` at `dca21ae`:** the groups sit at `rdf_persistence/model/technical/<group>/rp_<group>.yaml`,
  each its own `[[tool.rp-generate]]` target with `kind = "technical"`, generated into
  `rdf_persistence/services/generated/<group>/` (`service`, `templates`) or
  `adapters/generated` (`wire`); `technical-models` proposal DEC-2 names `telemetry` with PD-1's
  exact paths. PD-1 holds unchanged. Residual overlap: its tasks 3.2 and 3.3 change the
  constructors of `FusekiStore`, `ZitadelIdentity`, `S3FileStore`, `RedisEventBus`, `Relay` and
  `MessageBus`, the files of our tasks 1.3, 1.4 and 2.2; its 3.1 adds a target beside ours in
  `pyproject.toml`. Handling: rebase on `origin/develop` before each PR, resolve by P-0003 for
  generated files, follow its paths if they move; PD-13's `middlewares=` is placed after its
  settings group parameter in stage 2.
- **D-2 Authority** (developer, 2026-11-17): the lead commits, pushes, opens one PR per stage and
  merges after the local `make check-all` passes on the rebased branch and CI is green.
- **D-3 Review set.** MEDIUM, no `## Invariants` section: no adversarial tester (stage loop,
  Prepare). Per P-0005, stage 1 gets one L2+L3 pass and a checker; the full review (L1, L2, L3 as
  separate passes, L4+L5 as one) runs once, on stage 2, the end of the epic.
- **D-4 A dotted alias names no field** (task 1.1; corrects PD-1's premise that the generator
  "already renders" dotted aliases). linkml 1.12.1's `PydanticGenerator` names a field
  `underscore(slot.alias or slot.name)`, so `alias: rp.step` gives `rp_step` (and `ds.name` gave
  `rp_wire.py`'s `ds_name`). Extended in our generator (AGENTS.md principle 2):
  `SplitPydanticGenerator.after_generate_slot` names the field after the slot when its alias is
  not a Python identifier; the alias stays `Field(alias=…)`. Only `fuseki_dataset_name` changes
  outside this change (`ds_name` → `fuseki_dataset_name`, one use in `adapters/fuseki.py`).
  Camel-case wire aliases, valid identifiers, keep their present names. Rejected: the `rp_*`
  names (every TC and call site would change), an opt-in annotation (a second way to name a field).
- **D-5 mypy reads the field names** (tasks 1.2–1.4). Without a plugin mypy takes pydantic's
  `alias` as the only constructor keyword (PEP 681), so every `LogContext(step=…)` is a `call-arg`
  error although `validate_by_name` accepts it at run time. `mypy.ini` enables the stock
  `pydantic.mypy` plugin (P-0008: reuse). The plugin also types `model_construct()` with the
  required fields, which the one bare `TenantAccess.model_construct()` in `tenancy.py`
  (`_refuse_bad_store_name`) breaks; that call is fixed in the same commit. Rejected: `# type:
  ignore` at 100+ sites; generating `validation_alias` instead (the wire models validate by alias).
- **D-6 Carried to stage 2** (stage 1 review, no Critical). W1: the guard of PD-9 accepts a log
  call with no `extra=`, while DEC-8 and the spec ask `rp.step` on every record; task 2.1 makes
  the guard require `extra=log_extra(...)` on every call and corrects PD-9's wording ("any
  `extra=`" → "every call's `extra=`"). S3: the `error_type` slot's description names only the
  qualified class name; task 2.1 rewords it ("or the code a service answered with", PD-3) and
  regenerates.

- **D-7 TC-22's input** (stage 1 container lane, red). The test wrote a raw `xadd {"data": "{}"}`;
  FastStream decodes that body as JSON, so the handler's `raw: bytes` refuses it before
  `RedisEventBus` reads the envelope, and no warning is logged. The test, not the adapter, is
  wrong: it sends a bytes body with headers that are no valid envelope, so the adapter's own
  check refuses it.

- **D-8 Stage 2 order around `technical-models` stage 3.** PR #150 (its stage 3, rebased on our
  stage 1) changes the constructors of `RedisEventBus`, `Relay`, `MessageBus`, the kit and the HTTP
  adapters, the classes of tasks 2.2–2.4. Task 2.1 (new module, dependencies, lint bans, test
  fixtures) runs first on `develop` at `7381b03`; before 2.2 the branch is rebased on
  `origin/develop` (with #150 if merged by then), so the span work is written against the settings
  parameters. Then 2.2 ∥ 2.4 ∥ 2.6 (disjoint files), then 2.3 (TC-29 needs `TracedStore`), then 2.5.

**Stage 1, under the floor** (L2+L3 pass, `findings=5 accepted=0`; W1 and S3 carried by D-6):

- S1 `test_messagebus_adversarial.py:629,669,776` assert exception text through `caplog.text`
  (the traceback), not the record's `exc_info`. Correct today; style only.
- S2 TC-12's second half raises `MessageLimitExceeded` from an observer instead of a real commit;
  the real limit is covered at `test_receive.py:320-327`.
- S4 `_is_python_name`'s keyword branch has no test (no schema uses a keyword alias).
