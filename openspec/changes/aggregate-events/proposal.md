<!-- Parents: openspec/specs/rp-aggregate-store (one named graph per aggregate, guarded commits);
     architecture v1, docs/modules/ROOT/pages/architecture/index.adoc (building blocks: "Outbox,
     event bus and relay" and "server-sent events", deferred). Seeds: inputs/seed.md. -->

# EPIC: Aggregate events: outbox, event bus and server-sent events

> Candidate EPIC, shaped 2026-11-06 from the v1 future list. Not planned: the PLAN (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.
>
> **Re-shaped 2026-11-13 (logged).** The developer confirmed the need and widened it: "support event
> driven applications with design patterns and architecture described in the cosmic python book
> ... adopt popular libraries/frameworks if necessary". The in-process layer (domain events,
> commands, handlers, the message bus, the unit of work's events) moved to its own change,
> `message-bus`, which this EPIC now depends on. This EPIC keeps what crosses the process boundary,
> the book's chapter 11 plus the outbox it recommends: DEC-5 to DEC-8 below; the Solution outline,
> No-gos and What Changes are read with them, and DEC-5 to DEC-8 win where they differ.
>
> **Backlog position (2026-11-12):** after `atomic-commit` (hard: the outbox insert is one more operation of its transaction, DEC-6 there) and `collaboration-and-reference-collections` (whose No-gos defer notifications here). The capability descriptor of `second-store` must state that one update request is atomic; that is all this EPIC needs from it, so it no longer waits for the whole of `second-store`. Q-0 (a named need) is now answered by the consumer: notify on workflow transitions and comments (#80, #81). See `openspec/changes/README.md`.

**Golden-thread parent:** capability `rp-aggregate-store` (the commit) and the deferred building
blocks "Outbox, event bus and relay" and "server-sent events" of
`docs/modules/ROOT/pages/architecture/index.adoc`.

## Appetite

**LARGE.** Several related capabilities: an outbox written by the commit, a relay, a bus port with an
adapter, and a server-sent-events route with access checks. New boundaries: the service gains a
background worker and possibly a new container.

## Why

A v1 commit is one SPARQL update on the aggregate's graph and its registry entries
(`services/session.py`, `REPLACE`, `REMOVE`); nothing records that a change happened, and no code
outside the request learns of it. The architecture deferred the outbox because "no v1 need reacts to
a change in another aggregate". A need that does (a projection, a notification, a browser that
should refresh) can only poll today.

## Solution outline

Every successful commit records an event in the same update, so an event exists if and only if the
change does. A relay publishes recorded events to a bus at least once, in commit order per
aggregate. Code in the service can subscribe to the bus, and a client can follow the events of a
tenant over server-sent events, seeing only events about what it may read.

## Key decisions

- **DEC-1**: An event record is a LinkML class, generated with every other model artefact; events
  are built and read through generated models, not dicts. Source: D-13; PD-24; AGENTS.md.
- **DEC-2**: Write tracking stays statements about the graph IRI (D-7, PD-7); the event does not
  replace it.
- **DEC-3**: Access stays per tenant and per aggregate, decided by the in-process check (D-4,
  `rp-access`); a subscriber sees only what that check lets it read.
- **DEC-4**: Ports in `services`, implementations in `adapters`; adapters are tested against real
  containers (PD-1; archived DEC-4).
- **DEC-5** (developer, 2026-11-13): what is published is `message-bus`'s message, **one per
  commit**: the completed activity with its `prov:Generation`s and `prov:Invalidation`s (the fixed
  PROV event set; no other event kind). The outbox entry is one more operation of the commit's
  transaction (`atomic-commit`), so a message exists if and only if its change does. Order per
  aggregate follows from the versions; a server-sent-events reader receives the activity with the
  parts about aggregates it may not read removed.
- **DEC-6** (leader's choice, 2026-11-13, the developer may overrule): the broker is reached through
  **FastStream** behind the `EventBus` port: one library for Redis Streams, RabbitMQ, NATS and
  Kafka, pydantic messages (which the generated models are), and an AsyncAPI document generated
  from the subscribers. **Redis Streams first** (the book's choice, one light container); RabbitMQ
  is a configuration of the same adapter, proved in the conformance suite if time allows. The
  PLAN's first task is a spike on FastStream with the generated models. Rejected: hand-rolled
  `redis-py` as in the book (every broker would be new code); Celery or Dramatiq (task queues, not
  event streams).
- **DEC-7** (2026-11-13): incoming external events are handed to the message bus, so a handler does
  not care whether its event came from this process or another (the book's chapter 11). Consumers
  are idempotent by event id: the relay delivers at least once.
- **DEC-8** (2026-11-13): commands stay in process; only events cross the broker.
- **DEC-9** (developer, 2026-11-13; answers seed Q-4): messages are **thin** (`message-bus`
  DEC-12): references and version tokens, never the aggregate's triples. A subscriber reads the
  content with its own rights. Event-carried state (fat messages) is not in this EPIC; if a consumer
  ever needs it, it is an opt-in per aggregate class with its own decision.
- **DEC-10** (developer, 2026-11-13, "accept all recommendations"): the activity record (kept,
  `message-bus` DEC-10) **is** the outbox entry; a "published" mark replaces a separate outbox. The
  relay is a background task of the service, single instance; several instances need a lease,
  deferred. Server-sent-events clients resume (`Last-Event-ID`) within 7 days. DEC-6 (FastStream,
  Redis Streams first) is confirmed; messages travel as the generated JSON with a link to the
  JSON-LD context. Tenant-level events stay out (system database).

## Rabbit-holes

- **Exactly once.** Not achievable across a store and a bus; promise at least once and give events
  an identity for de-duplication.
- **Ordering across aggregates.** Only per-aggregate order is cheap.
- **Outbox growth.** Published events must be pruned, or the tenant database grows forever.
- **Several service instances.** v1 assumes a single instance for the sweep (PD-8b); several relays
  would publish twice.
- **Events of tenant creation and deletion.** They live in the system database, not a tenant's.

## No-gos

- Event sourcing: the graph stays the state; events are notifications.
- Sagas, process managers, or commands sent through the broker (commands stay in process, DEC-8).
- The in-process bus, handlers and the unit of work's events (`message-bus`).
- Replaying history from before this EPIC.
- WebSockets or a push service other than server-sent events.
- Any consumer term, model or code.

---

## What Changes

As delivered (the shaped text was: an event class, the outbox entry in the commit, a relay and a
port, a bus adapter, an SSE route, a fake bus and a bus container).

- `rdf_persistence/model/service/rp_service.yaml`: the wire class `EventEnvelope` and the optional
  setting `public_url`. No new event class: the message is `message-bus`'s activity (DEC-5).
- `services/session.py`: the commit's record marks the activity `rp:pendingSince` with the store's
  `NOW()`; reads and marks for the relay and the resume; `services/tenant_dump.py`: a restore drops
  the marks.
- `services/`: `events.py` (the `EventBus` port), `relay.py`, `decoding.py`, `event_hub.py`,
  `visible_part.py`, `event_stream.py`.
- `adapters/redis_events.py`: `RedisEventBus` on FastStream, in the new extra `events`.
- `entrypoints/`: `install_service(event_bus=)`, the relay in the lifespan, `kit.receive`
  (incoming events), the route `GET /{tenant}/rp-events` (`sse.py`).
- `testkit/`: `InMemoryEventBus`, `InMemoryBroker`, `event_bus_conformance`, a `redis` compose
  service and fixture.
- Docs: `howto/event-driven.adoc` (the relay, the event bus, server-sent events), the
  architecture page, the durations table, the questions.

## Capabilities

### New Capabilities

- `rp-events`: the outbox, the relay, the bus port, incoming events and the server-sent-events
  route.

### Modified Capabilities

None as deltas. One behaviour of `message-bus` changes, stated in the `rp-events` delta: an
overtaken commit (atomic-commit PD-4) is now published by the relay (PD-2).

## Impact

- Every recorded commit writes one more triple (the mark); the relay writes one update per
  activity. Not re-measured: `message-bus` measured the record at no cost above noise (RISK-2,
  accepted).
- `install_service` runs a background relay with or without an event bus; a broker (Redis 8.4+)
  is a deployment dependency only for a consumer that passes `event_bus`, and installs the extra.
- New public route `GET /{tenant}/rp-events`; new optional setting `public_url`.

## As built (2026-11-16)

Delivered in #124 (stages 1 and 2 as one PR, D-3) and in the stage 3 PR. The text above the
reconciled sections stays as shaped; this table says where the PLAN or the code departs from it
or adds to it. Every DEC held.

Not built, as the No-gos and the PLAN say: several relay instances or a lease (DEC-10, RISK-4),
RabbitMQ (DEC-6 "if time allows"), tenant-level events, server-sent events of the application
database, a hop limit across deployments (RISK-8). Left to issue #125: the review findings under
the floor (backoff and paging, stream caps, test and structure clean-ups).

| Shaped | Now | Decision | State |
|---|---|---|---|
| Solution outline: "an event exists if and only if the change does" | The commit marks its activity pending in the same update; records from before this EPIC are never pending, so no history is replayed | PD-1, PD-2 | built (#124) |
| DEC-10: a "published" mark | A pending mark, replaced by `rp:relayedAt` after the publish; a record that cannot be decoded is marked `rp:publicationFailed` | PD-1, PD-3 | built (#124) |
| DEC-5: order per aggregate follows from the versions | The store's `NOW()` at apply time orders a database's activities; the version chain settles ties; a malformed mark sorts last | PD-5, D-5 | built (#124) |
| DEC-6: FastStream, Redis Streams first | `RedisEventBus` on FastStream 0.7.8, redelivery by `claim_min_idle_time` (Redis 8.4+), a best-effort trim to 7 days, each publish bounded | PD-8, D-1, D-17, D-18 | built (#124; D-17, D-18 in stage 3) |
| DEC-7: incoming events go to the message bus | `kit.receive`: own origin skipped, the toolkit principal, a probe; unusable messages are acked, a store or migration failure redelivers | PD-10, D-6, D-8, D-19 | built (#124; D-19 in stage 3) |
| DEC-9, DEC-10: the generated JSON with a context link | `EventEnvelope` headers beside the activity's JSON; the link is `{public_url}{prefix}/context.jsonld` | PD-6, PD-7, D-4, D-16 | built (#124; D-16 in stage 3) |
| DEC-3: a subscriber sees only what it may read | Generations and invalidations of hidden aggregates removed; an activity about a hidden resource, or with nothing left, not sent; access re-read every second | PD-11, D-11 | built (stage 3) |
| DEC-10: SSE resume within 7 days | `Last-Event-ID` replays from `rp:relayedAt`; an unknown, malformed or expired id gets `reset` (with an empty data line); a closed slow reader resumes without loss | PD-12, D-10, D-14, D-21 | built (stage 3) |
| (not said) the stream's path and auth | `/{tenant}/rp-events` under the reserved prefix; bearer header only (a fetch-based client in browsers); a stream lasts 5 minutes, so a stale token cannot keep it open | D-13, D-15, D-20 | built (stage 3) |
| Rabbit-holes, "Outbox growth" | Nothing is deleted: the records are `message-bus`'s history; only the mark changes; the stream is trimmed | PD-13 | built (#124) |
| Impact: "the cost is measured" | Not re-measured; `message-bus` measured the record | RISK-2 | accepted |
| What Changes: "an event class" | None: the message is the activity (DEC-5) | DEC-5 | as decided |
