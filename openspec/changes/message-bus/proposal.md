<!-- Parents: openspec/specs/rp-aggregate-store (the unit of work and its commit); rp_provenance
     (Activity on PROV-O); the developer's direction of 2026-11-13 (event-driven applications as in
     Cosmic Python, messages integrated natively with PROV-O); split from aggregate-events.
     Seeds: inputs/seed.md. -->

# EPIC: Message bus: commands as PROV activities, a fixed set of PROV events

> Shaped 2026-11-13, split from `aggregate-events` (inputs/seed.md, "Why a separate change").
>
> **Re-shaped 2026-11-13 (logged, same day, before any PLAN).** The developer asked to integrate the
> messages natively with PROV-O and to keep the link to use cases light (inputs/seed.md, "Re-shape:
> PROV-O"). The first shape had consumer-declared `Event` and `Command` classes; this one has no
> event classes for consumers at all. Commands are `prov:Activity` subclasses in three layers, the
> events are a fixed PROV set, and one message is published per commit. Appetite grew from MEDIUM
> to LARGE (layer 2). Decisions marked "leader's choice" may be overruled by the developer.

**Golden-thread parent:** capability `rp-aggregate-store` (the unit of work); `rp_provenance.yaml`
(`Activity`, `prov:Activity`); the developer's direction (2026-11-13): "support event driven
applications with design patterns and architecture described in the cosmic python book" and
"integrate them natively, even adopt prov-o concepts".

## Appetite

**LARGE.** Several related capabilities: activity records written by every commit, the PROV event
set, the bus with its command and observer registries, and the standard commands of the toolkit's
existing features (layer 2). The unit of work and the commit change; every write path records an
activity.

## Why

A consumer that wants the Cosmic Python architecture writes today its own message bus, its own
way of learning what a commit changed, and its own audit trail, each differently. The named need
(MWB2 #80, #81) is to react to workflow transitions and comments. The general need is that an
application on the toolkit can be event-driven: a request becomes a command, a handler changes
aggregates in one transaction, and others react to what happened, knowing who did it and in which
use case. PROV-O already says this: an activity, carried out by an agent, generated and invalidated
entities. The toolkit models activities on PROV-O already (`rp_provenance.yaml`), and the
collaboration EPIC's `TransitionRecord` is one.

## Solution outline

```yaml
# consumer: mapping_activities.yaml (imports mapping.yaml; mapping.yaml never imports it)
classes:
  ApproveMapping:
    is_a: Transition             # a standard command, specialised (layer 3)
  PublishRelease:
    is_a: Activity               # a use case over several aggregates (layer 3)
    slots: [used_resource, release_notes]
```

```python
bus = bootstrap(uow=..., commands={PublishRelease: publish_release},
                observers={ApproveMapping: [notify_author], Activity: [refresh_views]})
await bus.handle(PublishRelease(used_resource=[m1, m2], release_notes="..."))
```

| Layer | Commands (Activity classes) | Handler | Defined by |
|---|---|---|---|
| 1. Aggregate | `Add`, `Replace`, `Remove` | the toolkit | toolkit, fixed |
| 2. Toolkit features | files (`Upload`, `DeleteFile`); collaboration (`Comment`, `Reply`, `Transition`, `AddMember`, `RemoveMember`); access (`Grant`, `Revoke`, `Prohibit`) | the toolkit | toolkit, grows with each EPIC |
| 3. Extensions, if any | `ApproveMapping`, `PublishRelease`, ... | the consumer, or the standard one it specialises | consumer |

Every commit records one activity (its class is the command; the toolkit fills in start, end and
the principal) and, for each aggregate it touched, a `prov:Generation` (added; replaced: the new
version) or a `prov:Invalidation` (removed; replaced: the old version). These are the only events.
After the commit, the bus hands the completed activity, with its generations and invalidations, to
the observers of its class and of every ancestor class. An app that uses only the generic API and
the toolkit's features needs no layer 3.

## Key decisions

- **DEC-1** (developer, 2026-11-13): the events are a **fixed PROV set**: `prov:Generation` and
  `prov:Invalidation` (both `prov:InstantaneousEvent`), each linked to its activity. Consumers
  model no event classes.
- **DEC-2** (developer, 2026-11-13): **one message per commit**: the completed activity with its
  generations and invalidations. Order per aggregate follows from the versions.
- **DEC-3** (developer, 2026-11-13): commands are `Activity` subclasses in three layers (table
  above). A command is the request; once committed, the same class is the stored record of what
  happened. The use case lives on the activity, never on an event.
- **DEC-4** (developer, 2026-11-13): an extension preferably specialises a standard command
  (`ApproveMapping is_a: Transition`); a use case over several aggregates is a bare `Activity`
  subclass with a consumer handler.
- **DEC-5** (developer, 2026-11-13): **dispatch follows the class hierarchy**, the one deliberate
  change from the book. A command goes to the handler of its nearest class that has one; its error
  reaches the caller. An observer registered for a class receives the activities of that class and
  its subclasses; an observer's error is logged and the others still run.
- **DEC-6** (developer, 2026-11-13): the generic HTTP routes do not go through the bus. The session
  records the standard activity on every commit and hands it to the bus afterwards, so a change has
  the same activity and observers wherever it came from.
- **DEC-7** (developer, 2026-11-13; also repository rule P-0001): consumers model use-case
  activities in a sibling LinkML module (`<domain>_activities.yaml`) that imports the domain's
  static module; the static module never imports it. The generator checks the direction (a stored
  class's slot never ranges over an activity class of layer 3) and refuses a consumer-set value for
  the slots the toolkit fills (start, end, principal).
- **DEC-8**: everything is LinkML (D-13; PD-24; AGENTS.md): the layer 1 and 2 classes and
  `Generation`, `Invalidation` extend `rp_provenance.yaml`, generated with every other model.
- **DEC-9**: events reach the bus only after the commit succeeded; a refused commit records no
  activity and publishes nothing (`atomic-commit` makes the commit all-or-nothing; the activity is
  one more operation of its transaction).
- **DEC-10** (leader's choice): activity records live in one provenance graph per tenant, not in
  the aggregates' graphs, and are kept as the audit trail (no pruning); write tracking on the graph
  IRI (D-7, PD-7) stays. A record survives the removal of the aggregates it names.
- **DEC-11** (leader's choice): the bus is hand-rolled, as in the book (inputs/seed.md lists the
  libraries checked); dependencies reach handlers through a `bootstrap` with `functools.partial`.
  In process only: an observer that has not run when the process stops is lost; durable delivery is
  `aggregate-events`.

## Rabbit-holes

- **Collaboration's records.** `TransitionRecord` (collaboration EPIC) becomes the layer-2
  `Transition`. That EPIC deletes the records about a removed resource (its PD-15); DEC-10 keeps
  activity records. The PLAN decides with the developer whether `Transition` records follow PD-15
  or DEC-10; until then nothing in the collaboration EPIC changes.
- **The exact PROV shape.** Qualified `prov:Generation` nodes linked by `prov:activity`, the version
  token on them, and how the activity-centred message maps to them are fixed in the PLAN with a
  round-trip test (RDF, JSON-LD, the generated model).
- **Commit cost.** One activity and one generation or invalidation per aggregate on every commit;
  measured in the PLAN, as `aggregate-events` measures the outbox.
- **Tenancy commands** (`CreateTenant`, `DeleteTenant`, `Restore`) act in the system database, not a
  tenant's; not in this EPIC.
- **Loops.** An observer that sends the command it observes loops; cap the messages one `handle`
  call processes, nothing cleverer.
- **Hidden aggregates.** Observers run with the toolkit's rights; filtering by reader belongs to
  server-sent events (`aggregate-events`).

## No-gos

- A broker, an outbox, server-sent events (`aggregate-events`).
- Event sourcing: the graph stays the state; activities are history, not the source of state.
- Consumer-declared event classes.
- Sagas, process managers, retries with back-off, scheduled commands.
- Tenancy activities (system database).
- A dependency-injection library.
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/model/rp_provenance.yaml`: `Generation`, `Invalidation`, the layer 1 and 2
  activity classes and their slots; `make generate`.
- `rdf_persistence/services/session.py`: every commit records its activity in the transaction.
- `rdf_persistence/services/messagebus.py` (new): `MessageBus`, `bootstrap`; `UnitOfWork` takes the
  command it serves and hands the completed activity to the bus.
- `rdf_persistence/generation/checks/`: the import direction and the toolkit-filled slots (DEC-7).
- `rdf_persistence/testkit/`: a recording observer and a fake bus for consumer tests.
- Docs: `architecture/index.adoc` (building block), `howto/adopt.adoc` (an event-driven
  application; modelling use-case activities), `questions.adoc`.

## Capabilities

### New Capabilities

- `rp-messages`: activity records, the PROV events, the bus, commands and observers.

### Modified Capabilities

None as deltas here; the commit writing an activity is stated in `rp-messages`.

## Impact

- Every commit writes an activity: more triples per commit, measured.
- `aggregate-events` publishes these activity messages; it stores no other event kind.
- The collaboration EPIC's `TransitionRecord` is adopted as layer 2 (Rabbit-holes).
