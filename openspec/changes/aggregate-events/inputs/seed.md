<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: events

## Seed text

From `docs/modules/ROOT/pages/questions.adoc`, "What could strengthen it in the future":

> *Events*: an outbox, an event bus and server-sent events, deferred until a need reacts to a
> change in another aggregate.

From `docs/modules/ROOT/pages/architecture/index.adoc`, building blocks:

> |Outbox, event bus and relay |deferred |No v1 need reacts to a change in another aggregate.
>
> |Annotation sets, forms from shapes, schema migrations, server-sent events |deferred |No v1 need.

From the archived `toolkit-v1-foundation/proposal.md`, No-gos:

> A second store (Oxigraph, Virtuoso), the outbox, events and server-sent events, schema migrations,
> and forms from shapes.

## What the code does today (checked 2026-11-06)

- `rdf_persistence/services/session.py`: `add_graph`, `replace_graph`, `remove` each send one
  SPARQL update (templates `ADD`, `REPLACE`, `REMOVE`) and confirm it with an `ASK`. No outbox, no
  callback, no hook after a commit.
- `rdf_persistence/entrypoints/service.py`: `install_service` adds a lifespan step (system database,
  role definitions, sweep); no background task.

## Open questions for the developer

0. **Is there a need now?** The seed defers events "until a need reacts to a change in another
   aggregate". Which need justifies this EPIC, and does it need all three parts (outbox, bus, SSE)
   or only one? Without a named need, the EPIC stays a candidate.
1. **Where does the outbox live?**
   - (a) A graph in the tenant database (`{tenant_iri}/outbox`), written in the commit's update:
     atomic with the change by construction.
   - (b) A table outside the store (Postgres, Redis): easier to consume; not atomic with a SPARQL
     update, which defeats the outbox.
2. **Which bus?**
   - (a) In process only (asyncio queues): no new container; events are lost for other instances.
   - (b) Redis Streams or NATS JetStream: durable, several consumers; one more container to run.
   - (c) None: SSE reads the outbox directly. Fewest parts; every SSE client polls the store.
3. **How is the relay run, given a single instance today?** A lifespan background task, a separate
   process, or a library call the consumer schedules? Several instances need a lease.
4. **What does an event carry?** (a) aggregate IRI, type, change kind, version, time, committer;
   (b) also the new content. (a) keeps events small and leaks less; (b) saves a read.
5. **How long are events kept?** Pruned after publish, kept N days for SSE resume
   (`Last-Event-ID`), or kept forever as an audit trail?
6. **Tenant-level events** (created, deleted, grants changed): in scope, and in which database?
7. **SSE access re-check.** Is a caller's access read once at connect, or re-checked when grants
   change during the stream?

## Developer answers (2026-11-06)

Developer: "whatever is best, i would not mind to have an event bus like redis/rabbitmq, but
we need also the necessary plumbing for event driven app in the code, no?"
- Leader's choice (2026-11-06), answering Q-1 and Q-2:
  - An outbox written in the same commit (at-least-once delivery).
  - A relay to an external bus (Redis Streams or RabbitMQ) behind an `EventBus` port, with a fake
    in the testkit.
  - In-process plumbing: domain events collected by the unit of work, and a message bus that
    dispatches them to handlers (cosmic-python's message bus).
  - Server-sent events for clients.
- Q-0 ("is there a need now?") stays with the developer. The answer reads as "build the plumbing",
  but no consumer need is named yet.
- Still open: Q-0, Q-3 to Q-7.

Developer: "accept recommendations, and continue" (2026-11-06).
- Accepted: a live event stream re-checks the caller's access when grants change.
- Every question still open: the leader drafts a recommendation when the PLAN is derived, and the developer accepted recommendations by default (2026-11-06). Each one is recorded in the PLAN as the leader's choice, and the developer may overrule it.

## Test scenarios the EPIC must prove

- Create, replace and remove each record exactly one event, in the same update.
- A refused commit (stale, invalid body, forbidden) records no event.
- After a crash between commit and publish, the event is published on restart.
- Events of one aggregate arrive in commit order; duplicates carry the same event id.
- An SSE client receives events of its tenant only, and none about aggregates it may not read.
- An SSE client that reconnects with `Last-Event-ID` receives what it missed, within retention.
- Published events are pruned according to the retention rule.
- The fake bus and the real bus pass the same conformance cases.
