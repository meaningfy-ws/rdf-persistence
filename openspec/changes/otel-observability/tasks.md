> Derives from: EPIC `otel-observability` (proposal.md). Two stages, one PR each into `develop`.
> Type: Implementation. Starts after `manual-revision-notes` (A-7, the `problems.py` record) and
> `technical-models` (PD-1) have merged.

`PD-n` is a decision of [design.md](design.md). Each log call's message, step and slots are the
row of [design.md PD-6](design.md#decisions) for that call; a task below names the rows it
covers, never restates them. Test files are under `tests/unit/services/` unless a path is given.
`attributes(r)` and `records_of(caplog, step)` are
the helpers of `tests/logs.py` (PD-10); `spans` is the conftest fixture of PD-10. `D` is a
`FakeStore`; `T` a tenant of the toy library (`tests/toy.py`).

**How it succeeds:** every TC below passes as a test; `tests/unit/test_log_calls.py` passes over the
whole package; the spans of the feature file appear under one trace; importing the package loads
no `opentelemetry.sdk` module. **How it fails:** a log call in the old style, a span missing an
attribute of PD-2/PD-5, a tenant marker found in a record or span, or the SDK imported by the
package; each is a failing test named below.

Every task is test first: write the TC rows as failing tests, then the code. Gate: `make
test-changed check-quality`, or `make test-fast check-quality` where the task says so. After a
schema change the lead runs `make check-generated`.

## Stage 1: one log context, one logging style (PR 1)

- [ ] 1.1 PD-1, PD-2, PD-3 (`log_extra`, `error_type`), PD-10 (helpers), PD-12: `model/technical/telemetry/rp_telemetry.yaml`
  with `LogContext` and its `[[tool.rp-generate]]` target in `pyproject.toml`; `make generate`; `services/telemetry.py` with
  `log_extra` and `error_type`; `opentelemetry-sdk` in the `test` group of `pyproject.toml` (the API's release in
  the lock); `tests/logs.py`. Layer: technical model, services. Tests in
  `tests/unit/services/test_telemetry.py`. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `log_extra(LogContext(step="x", tenant_id="t"))` | `{"rp.step": "x", "rp.tenant.id": "t"}`; no `None` values |
| TC-02 | `LogContext()`; `LogContext(step="x", tenant="t")` | each a `ValidationError` (missing `step`; unknown field) |
| TC-03 | `LogContext(step="x", blob_count="many")`; `policy_fields="a"` | each a `ValidationError` |
| TC-04 | every alias of `LogContext`; a `log.info("m", extra=log_extra(full))` with every slot set | each alias holds a dot and is not a `LogRecord` attribute; the record carries all 28 keys; no `KeyError` |
| TC-05 | the stable aliases of PD-2 | each equals its constant in `opentelemetry.semconv.attributes` |
| TC-06 | the two development aliases of PD-2 | equal the v1.45.0 table in the test (`messaging.system.name`, `messaging.destination.name`) |
| TC-38 | `error_type(NotFound("n"))`; `error_type(ValueError())` | `"rdf_persistence.domain.exceptions.NotFound"`; `"builtins.ValueError"` |

- [ ] 1.2 PD-6 (rows `iri_policy_guard.py` to `tenant_sweep.py`), PD-7: the 19 `extra=` sites of design Context, in `services/sweep.py`,
  `tenancy.py` (`_log_step`, the cleanup warning), `tenant_sweep.py` (`_log_removal`, the blob
  warning), `tenant_dump.py`, `file_removal.py`, `migration_runner.py` (`_failure` deleted, the
  `str(error)` messages gone), `iri_policy_guard.py` (constant message; the raised
  `IriPolicyChanged` keeps naming the fields). The tests that read old keys move to the new names
  through `tests/logs.py`: `test_migration_runner.py`, `test_migration_runner_adversarial.py`,
  `test_tenant_dump.py`, `test_tenant_sweep.py`, `test_sweep.py`, `test_iri_policy_guard.py`,
  `test_tenancy.py`, `test_tenancy_stores.py`, `test_remove_with_files.py`,
  `test_tenant_stores_adversarial.py`. Layer: services. Gate: `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-07 | `sweep` with an orphan `lib-t-zzzz` on `client-a` | an INFO record, message `dropping an orphan database`, `rp.step=drop-orphan-database`, `db.namespace=lib-t-zzzz`, `rp.store.name=client-a` |
| TC-08 | `migrate_tenants` where one tenant's update raises `StoreUnavailable("down")` | one ERROR record, constant message, `rp.step=migrate-tenant`, `rp.tenant.id`, `rp.schema.id`, `rp.migration.name=1__2 of …`; `exc_info` holds the error whose text has `down`; no `cause` attribute |
| TC-09 | `guard_iri_policy` with a changed policy | one ERROR record, constant message, `rp.iri_policy.fields` a list naming the fields; `IriPolicyChanged` raised, its message naming them |
| TC-10 | a misplaced tenant (`test_sweep.py:305`) | `rp.store.name` the recorded store, `rp.store.found_name` the other |

- [ ] 1.3 PD-6 (rows `kit.py` to `session.py`, and `problems.py`), PD-7, PD-8: the interpolated
  calls in `services/session.py`, `services/relay.py`, `services/messagebus.py` and
  `entrypoints/kit.py`; the `extra=` of `entrypoints/problems.py`. Tests moved:
  `test_session_activity.py`, `test_session_activity_adversarial.py`, `test_relay.py`,
  `test_relay_adversarial.py`, `test_messagebus.py`, `test_messagebus_adversarial.py`,
  `tests/unit/entrypoints/test_receive.py`, `tests/unit/entrypoints/test_problems.py` (its record
  gains `rp.step`), `tests/feature/test_messages.py`. Layer: services, entrypoints. Gate: `make test-fast
  check-quality` (the bus sits under every collaboration module).

| ID | Input | Expected |
|---|---|---|
| TC-11 | `kit.receive` of an event whose body fails validation and contains `secret-tenant-text` | one WARNING, constant message, `error.type`, `rp.error.detail` naming `started_at_time`; the marker in no message, attribute or `exc_info` |
| TC-12 | an observer that raises; then a commit over the message limit through `kit.receive` | one ERROR `an observer failed` with `rp.observer.name`, `rp.activity.id`, `exc_info`; one ERROR for the limit, with `rp.message.limit`, and only one |
| TC-13a | the relay: a publish that fails; a tenant database gone | WARNING with `rp.activity.id`, `rp.tenant.id`, `exc_info`; DEBUG with `rp.tenant.id`, `rp.step=relay-database-gone` |
| TC-13b | a commit overtaken (`session.py:1509`); an `on_commit` hook that raises | WARNING with `rp.activity.id`; ERROR with `rp.activity.id` and `exc_info` |
| TC-13c | a route raising `StoredDataInvalid` (a mapped kind answered 500: the `problems.py` record; an unmapped `RuntimeError` is the server's to log, `manual-revision-notes` TC-33b) | one ERROR `internal error answered`, `error.type=rdf_persistence.domain.exceptions.StoredDataInvalid`, `rp.step=answer-internal-error`, `exc_info` set |
| TC-13d | `kit.receive` of an event for a tenant this deployment lacks | one WARNING, `rp.activity.id`, `rp.tenant.id`, `error.type` ending `DatabaseGone` or `NotFound`; the tenant IRI in no message |

- [ ] 1.4 PD-6 (adapter rows), PD-8: the adapters `fuseki.py`, `zitadel.py`, `s3.py`, `redis_events.py`
  (`logger` renamed `log`). Tests moved: `test_fuseki_store.py:243`, `test_zitadel.py:388-389`,
  `tests/integration/adapters/test_redis_events.py:76-81`. Layer: adapters. Gate: `make
  test-changed check-quality`; the lead runs the Redis test in the container lane.

| ID | Input | Expected |
|---|---|---|
| TC-19 | Fuseki answers 400 with a body | DEBUG record, `db.response.status_code="400"`, `rp.store.response_body` the body; nothing above DEBUG |
| TC-20 | Zitadel answers 500 with `body-with-secrets` | DEBUG record, `http.response.status_code=500`; the body in no record |
| TC-21 | S3 refuses with `AccessDenied` (a code the adapter does not map); then with `NoSuchBucket` | DEBUG record, `error.type=AccessDenied`; for `NoSuchBucket` no record (it is mapped before the log) |
| TC-22 | a Redis message without a valid envelope | WARNING, `messaging.system.name=redis`, `messaging.destination.name` the stream |

- [ ] 1.5 PD-9: `tests/unit/test_log_calls.py`. Gate: `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-23 | the package (generated code excluded) | passes: every log call has one string-literal argument, `extra=` only as `log_extra(...)`, loggers named `log` |
| TC-24 | synthetic sources: an f-string message; `"m %s", x`; `extra={"step": …}`; `logger = getLogger(…)` | each reported, naming file and line |

Stage 1 closes with the lead's `make check-all` and `make test-containers`, the review set, the
fix pass, rebase on `develop`, PR 1 (BREAKING in its body, DEC-10), merge on green CI.

## Stage 2: spans, the broker seam, BDD and docs (PR 2)

- [ ] 2.1 DEC-4, DEC-5, PD-3 (`tracer`, `traced`), PD-10 (`spans` fixture), PD-11:
  `opentelemetry-api>=1.44,<2` in `[project] dependencies`; the TID251 ban of
  `opentelemetry.sdk` in `ruff.toml`; `services.telemetry` in the `.importlinter` bus list;
  `tests/conftest.py` fixtures; `tests/unit/test_packaging.py` check. Tests in
  `tests/unit/services/test_telemetry.py`. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-14 | in a subprocess with no provider set: `with traced("rp.x", LogContext(step="x"))` | runs; `trace.get_current_span().is_recording()` is false inside |
| TC-15 | `with traced("rp.x", LogContext(step="x", tenant_id="t"))` under the fixture | one finished span `rp.x`, kind INTERNAL, attributes `{"rp.step": "x", "rp.tenant.id": "t"}`, status UNSET |
| TC-16 | the block raises `NotFound("n")` | the same object re-raised; span status ERROR, one `exception` event, `error.type=rdf_persistence.domain.exceptions.NotFound` |
| TC-17 | subprocess: import `rdf_persistence`, `rdf_persistence.entrypoints.kit`, `rdf_persistence.adapters.fuseki` | no key of `sys.modules` starts with `opentelemetry.sdk` |

- [ ] 2.2 DEC-6, DEC-11, PD-4, PD-13: `TracedStore`, `system_name_of`, the kit's wrapping,
  `db_system_name` on `FusekiStore` and `FakeStore`, `RedisEventBus(middlewares=)`. Tests in
  `tests/unit/services/test_store.py`, `tests/unit/entrypoints/test_kit_stores.py`,
  `tests/integration/adapters/test_redis_events.py`. Layer: services, entrypoints, adapters,
  testkit. Gate: `make test-fast check-quality` (a port's wrapper), then the lead's
  `make test-containers TEST_PATH=tests/integration/adapters/test_redis_events.py`.

| ID | Input | Expected |
|---|---|---|
| TC-25 | each of the 8 port methods on `TracedStore(D, "rdflib")` | one CLIENT span named after the method; `db.system.name=rdflib`, `db.operation.name` the method, `db.namespace` the dataset (absent for `list_datasets`) |
| TC-26 | `system_name_of` of a `FusekiStore`; of an object without the attribute | `fuseki`; `sparql` |
| TC-27 | a kit wired to `D` and `client-a`; one query through each | spans on both, `db.namespace` each store's dataset; the same raw store under two names still raises `ValueError` (tenant-stores PD-16) |
| TC-18 | an update whose SPARQL holds the literal `secret-tenant-text` | no attribute of any span contains it; no `db.query.text` |
| TC-28 | `RedisEventBus(..., middlewares=[RedisTelemetryMiddleware()])`; publish, then receive (container) | a PRODUCER and a CONSUMER span with one trace id; the envelope reads back unchanged |

- [ ] 2.3 PD-5: spans in `Transaction.commit`, `migrate_shared`, `migrate_tenants`,
  `migrate_database`, `_apply`, `sweep`, `sweep_tenant`. Tests in
  `tests/unit/services/test_session_spans.py`, `test_migration_runner.py`, `test_sweep.py`,
  `test_tenant_sweep.py`. Layer: services. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-29 | a commit of one book on `T` through a `ToolkitStore(TracedStore(D))` | `rp.session.commit` with `db.namespace` of `T`; the store's `update` span is its child |
| TC-30 | a commit with no roots | no `rp.session.commit` span |
| TC-31 | a commit that raises `Conflict` | `rp.session.commit` ERROR, `error.type` ending `Conflict` |
| TC-32 | `migrate_tenants` with one pending migration on two tenants | `rp.migration.tenants` › 2 × `rp.migration.database` › `rp.migration.apply` with `rp.schema.id`, `rp.migration.name` |
| TC-33 | `sweep` with one orphan; `sweep_tenant` on `T` | one `rp.sweep` span with the `drop_dataset` span inside; one `rp.tenant_sweep` with `rp.tenant.id` |

- [ ] 2.4 PD-5: spans in `Relay.run_once`, `Relay._relay_database`, `MessageBus._start`,
  `MessageBus.publish`. Tests in `test_relay.py`, `test_messagebus.py`. Layer: services. Gate:
  `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-34 | `run_once` over two active tenants, called inside an open span `outer` | one `rp.relay.round` with no parent and a trace id other than `outer`'s, two `rp.relay.database` children with `rp.tenant.id` |
| TC-35 | a relay database whose session raises | that `rp.relay.database` ERROR; the round's span UNSET; the next tenant still relayed |
| TC-36 | a command whose handler queues a second command | two `rp.bus.handle` spans with `rp.activity.class`, `rp.activity.id` |
| TC-37 | two observers, the first raising | two `rp.bus.observe` spans, the first ERROR; the second observer ran |

- [ ] 2.5 BDD: `tests/feature/observability.feature` with the spec delta's scenarios, steps in
  `tests/feature/test_observability.py` on the toy service with `FakeStore`. The scenario "no
  provider" is TC-14 and "no SDK in the package" is TC-17. Gate: `make test-changed check-quality`.

- [ ] 2.6 DEC-10, DEC-11: `docs/modules/ROOT/pages/howto/observability.adoc` ("See what the toolkit
  is doing"): installing the SDK and an exporter; FastAPI's native telemetry
  (`FastAPI(telemetry=…)`); `HTTPXClientInstrumentor` before the stores are built;
  `RedisTelemetryMiddleware` through `RedisEventBus(middlewares=)`; the logging bridge (the
  handler of the SDK release in the lock, and where it moved); the spans of PD-5 and the
  attributes of PD-2; the old-to-new attribute table (DEC-10); sampling for RISK-5; what never
  reaches telemetry (RISK-3). Its nav line, its entry in `questions.adoc`, a pointer from
  `howto/adopt.adoc`'s wiring step, and a BREAKING line for the CHANGELOG in the PR body. Gate:
  `make check-docs`.

Stage 2 closes like stage 1. Then the reconciliation of `proposal.md` (an "As built" section), in
PR 2 before it merges.

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 1.4 · [ ] 1.5 · PR 1 · [ ] 2.1 · [ ] 2.2 · [ ] 2.3 · [ ] 2.4 ·
  [ ] 2.5 · [ ] 2.6 · reconcile · PR 2

## Verification

The TC tables as tests; `make check-all` and `make test-containers` before each PR;
`openspec validate otel-observability --strict`; the clarity gate on this pair ([evidence/clarity-gate.md](evidence/clarity-gate.md)).
