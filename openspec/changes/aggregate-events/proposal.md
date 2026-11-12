<!-- Parents: openspec/specs/rp-aggregate-store (one named graph per aggregate, guarded commits);
     architecture v1, docs/modules/ROOT/pages/architecture/index.adoc (building blocks: "Outbox,
     event bus and relay" and "server-sent events", deferred). Seeds: inputs/seed.md. -->

# EPIC: Aggregate events: outbox, event bus and server-sent events

> Candidate EPIC, shaped 2026-11-06 from the v1 future list. Not planned: the PLAN (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.
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
- Sagas, process managers or commands sent through the bus.
- Replaying history from before this EPIC.
- WebSockets or a push service other than server-sent events.
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/model/`: an event class (a new module or `rp_core`; open question).
- `rdf_persistence/services/session.py`: the commit writes the outbox entry in its update.
- `rdf_persistence/services/`: a relay and an event-bus port; `adapters/`: a bus adapter.
- `rdf_persistence/entrypoints/`: a server-sent-events route under the tenant.
- `rdf_persistence/testkit/`: a fake bus; a container for the bus if one is chosen.

## Capabilities

### New Capabilities

- `rp-events`: the outbox, the relay, the bus port and the server-sent-events route.

### Modified Capabilities

None.

## Impact

- Every commit writes more; the cost is measured.
- `install_service` gains a background relay and the route; a bus may become a deployment dependency.
