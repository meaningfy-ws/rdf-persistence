# rp-observability Specification

## Purpose
What the toolkit tells an application about itself through OpenTelemetry: the spans it starts
through the API, the attributes of its spans and log records, its one logging style, the tenant
data it keeps out of both, and what it leaves to the application (the SDK, exporters, providers
and handlers). Created by `otel-observability` (archive/2026-11-17-otel-observability).

## Requirements

### Requirement: The library traces through the OpenTelemetry API only

The toolkit SHALL start spans through `opentelemetry-api` only. It SHALL NOT install or configure a
tracer provider, logger provider, exporter, processor, sampler, logging handler, formatter or
level, in the package or in its testkit. Without a provider installed by the application its spans
SHALL be no-ops and its behaviour SHALL be unchanged.

#### Scenario: no provider installed
- **GIVEN** an application that installs no OpenTelemetry SDK
- **WHEN** it commits a book
- **THEN** the commit succeeds as before and no span is recording

#### Scenario: the package loads no SDK
- **GIVEN** a fresh interpreter
- **WHEN** the package, its kit and its Fuseki adapter are imported
- **THEN** no `opentelemetry.sdk` module is loaded

### Requirement: Store calls are traced with database conventions

Each call of the `Store` port made through the service kit SHALL be one CLIENT span named after the
port operation, with the attributes `db.system.name`, `db.operation.name` and, when the call
names a dataset, `db.namespace` (OpenTelemetry semantic conventions v1.45.0). A span SHALL NOT
carry the SPARQL text, a request or response body, or any value of a tenant's data. A call that
raises SHALL leave its span with status ERROR, the exception recorded, and `error.type` set to the
exception's qualified class name; the exception SHALL propagate unchanged.

#### Scenario: a commit's store call
- **GIVEN** an application with a tracer provider and a kit on a Fuseki store
- **WHEN** a book is committed in tenant `T`
- **THEN** an `update` span with `db.system.name` `fuseki` and `db.namespace` the tenant's database is a child of the commit's span

#### Scenario: a failing store call
- **GIVEN** a store that does not answer
- **WHEN** a book is read
- **THEN** the `query` span has status ERROR and `error.type` ending in `StoreUnavailable`, and the read raises `StoreUnavailable` as before

#### Scenario: tenant data stays out of spans
- **GIVEN** a book whose title is `secret-tenant-text`
- **WHEN** it is committed
- **THEN** no span attribute contains `secret-tenant-text`

### Requirement: The toolkit's own work is traced

The toolkit SHALL open an INTERNAL span named `rp.<area>.<action>` around each commit that sends a
request, each migration run, database and applied migration, the start-up sweep, each live-tenant
sweep, each relay round and each tenant database in it, and each message-bus handler and observer
call. Span names SHALL NOT contain identifiers; identifiers SHALL be attributes.

#### Scenario: one request, one trace
- **GIVEN** an application with a tracer provider and an observer of `Activity`
- **WHEN** a book is committed
- **THEN** the commit span, its store spans and the observer's span share one trace

#### Scenario: a relay round
- **GIVEN** two active tenants with pending activities
- **WHEN** the relay runs one round
- **THEN** one `rp.relay.round` span holds one `rp.relay.database` span per tenant, each naming its tenant in `rp.tenant.id`

### Requirement: Log records carry a constant message and conventional attributes

Every log record the toolkit writes SHALL have a constant message, and its attributes SHALL come
from the generated `LogContext` model only: OpenTelemetry semantic-convention names where the
conventions define one (`db.*`, `error.type`, `http.*`, `messaging.*`), `rp.*` names otherwise,
and always `rp.step`. A record of a failure SHALL carry the exception in `exc_info`, except where
the exception's text can carry a tenant's data, where it SHALL carry `error.type` and a detail
that names fields and never values. The same model SHALL give span attributes their names.
The toolkit SHALL log an error only where it handles it, except a start-up refusal that stops the
process.

#### Scenario: an orphan database dropped
- **GIVEN** an orphan database `lib-t-zzzz` on the store `client-a`
- **WHEN** the start-up sweep drops it
- **THEN** one INFO record says `dropping an orphan database` with `rp.step` `drop-orphan-database`, `db.namespace` `lib-t-zzzz` and `rp.store.name` `client-a`

#### Scenario: a tenant's migration fails
- **GIVEN** a tenant whose migration request fails
- **WHEN** the tenants are migrated at start-up
- **THEN** one ERROR record names the tenant, the schema and the migration as attributes, and carries the failure in `exc_info`

#### Scenario: an invalid incoming event
- **GIVEN** an incoming event whose body fails validation and contains `secret-tenant-text`
- **WHEN** the kit receives it
- **THEN** one WARNING record carries `error.type` and the field at fault, and `secret-tenant-text` appears nowhere in the record

#### Scenario: the message limit reached through an incoming event
- **GIVEN** a message bus with a limit, and an incoming event whose commands exceed it
- **WHEN** the kit receives it
- **THEN** exactly one ERROR record reports it, with `rp.message.limit`

### Requirement: The application can trace the event broker

The Redis event bus SHALL accept broker middlewares from the application and SHALL pass them to
its broker unchanged, so the application can add the broker's own telemetry middleware. The
toolkit SHALL install none.

#### Scenario: a traced event
- **GIVEN** a Redis event bus built with the broker's telemetry middleware and a tracer provider
- **WHEN** an event is published and received
- **THEN** the publish and the receive spans share one trace, and the envelope reads back unchanged
