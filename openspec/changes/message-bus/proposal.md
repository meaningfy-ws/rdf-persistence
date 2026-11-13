<!-- Parents: openspec/specs/rp-aggregate-store (the unit of work and its commit); the developer's
     direction of 2026-11-13 (event-driven applications as in Cosmic Python); split from
     aggregate-events. Seeds: inputs/seed.md. -->

# EPIC: Message bus: domain events, commands and handlers in process

> Shaped 2026-11-13, split from `aggregate-events` (inputs/seed.md, "Why a separate change"). Open
> questions answered by the lead; the developer may overrule any DEC marked "leader's choice". Not
> planned: the PLAN is derived at the start of its epic session.

**Golden-thread parent:** capability `rp-aggregate-store` (the unit of work); the developer's
direction (2026-11-13): "support event driven applications with design patterns and architecture
described in the cosmic python book".

## Appetite

**MEDIUM.** One new capability (messages, a bus, handlers, the unit of work's event collection)
with its tests and docs; the unit of work is touched lightly.

## Why

A consumer that wants the Cosmic Python architecture writes today its own message bus and its own
way of learning what a commit changed, and every consumer would write them differently. The named
need (MWB2 #80, #81) is to react to workflow transitions and comments; the general need is that an
application built on the toolkit can be event-driven: a request becomes a command, a handler changes
one aggregate, the change raises events, and other handlers react in their own transactions.

## Solution outline

```python
class ApproveMapping(Command): ...            # LinkML classes, is_a Command / Event
class MappingApproved(Event): ...

async def approve(cmd: ApproveMapping, uow: UnitOfWork) -> None:
    mapping = await uow.get(cmd.mapping)
    ...                                       # change it
    uow.raise_event(MappingApproved(mapping=cmd.mapping))
    await uow.commit()                        # events leave only if this succeeds

bus = bootstrap(uow=lambda: session.unit_of_work(), commands={ApproveMapping: approve},
                events={MappingApproved: [notify_reviewers], AggregateReplaced: [refresh_view]})
await bus.handle(ApproveMapping(mapping=iri))
```

The unit of work collects the events handlers raise and the toolkit's own change events
(`AggregateAdded`, `AggregateReplaced`, `AggregateRemoved`) of every committed root. After a
successful commit the bus takes them and dispatches them; a refused commit drops them.

## Key decisions

- **DEC-1**: The book's semantics. A command has exactly one handler and its error reaches the
  caller; an event has zero or more handlers, each runs, and an error is logged without stopping the
  others. Events raised while handling are queued and handled in the same `handle` call.
- **DEC-2**: Messages are LinkML classes (D-13; PD-24; AGENTS.md): abstract `Event` and `Command` in
  the toolkit schema, the three change events generated with the other models; consumers declare
  their messages `is_a: Event` or `is_a: Command` in their own schema.
- **DEC-3**: Events leave the unit of work only after its commit succeeded (`atomic-commit` makes
  the commit all-or-nothing, so the events match the stored change).
- **DEC-4** (leader's choice): the bus is hand-rolled, as in the book; no library (inputs/seed.md
  lists those checked). Dependencies reach handlers by a `bootstrap` that binds them with
  `functools.partial`; the composition root stays the consumer's.
- **DEC-5** (leader's choice): in process only. An event raised by a commit is lost if the process
  stops before its handlers run; durable delivery is `aggregate-events` (the outbox). The docs say so.
- **DEC-6**: Ports in `services`, no new adapter; the generic HTTP routes keep calling the session
  directly, and a consumer's own route sends a command to the bus.

## Rabbit-holes

- **One aggregate per handler's transaction.** The book's rule; handlers that must change two
  aggregates atomically use the transaction (`atomic-commit`) instead of events. Say so in the docs;
  do not enforce it.
- **Event loops.** A handler raising the event it handles loops forever. Cap the messages one
  `handle` call processes (a limit with a clear error), nothing cleverer.
- **Read models (CQRS).** The book's view tables are consumer work; the toolkit's change events are
  enough to maintain them. No read-model framework.

## No-gos

- A broker, an outbox, server-sent events (all `aggregate-events`).
- Event sourcing: the graph stays the state.
- Sagas, process managers, retries with back-off, scheduled commands.
- A dependency-injection library.
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/model/`: `Event`, `Command` and the three change events (a new `rp_messages`
  module); `make generate`.
- `rdf_persistence/services/`: `messagebus.py` (`MessageBus`, `bootstrap`); `UnitOfWork` gains
  `raise_event` and `collect_new_events`, and records the change events of committed roots.
- `rdf_persistence/testkit/`: a recording handler and a fake bus for consumer tests.
- Docs: `architecture/index.adoc` (building block), `howto/adopt.adoc` (an event-driven
  application), `questions.adoc`.

## Capabilities

### New Capabilities

- `rp-messages`: messages, the bus, handlers and the unit of work's events.

### Modified Capabilities

None (the unit of work gains methods; its commit semantics are `atomic-commit`'s).

## Impact

- Additive: code that does not use the bus is unchanged.
- `aggregate-events` builds on these classes: the outbox stores the same events.
