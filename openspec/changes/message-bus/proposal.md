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

> **Narrowed 2026-11-14 (logged, in the epic session, before the PLAN was gated).** The code has no
> add-member, remove-member or upload operation, and grants are one "set grants" call on the system
> database (a No-go). The developer accepted (inputs/seed.md, "Question round of the epic
> session"): layer 2 in this EPIC is `Transition`, `PostComment`, `PostReply` (the names `Comment`
> and `Grant` are stored classes already) and `DeleteFile`; toolkit handlers exist for `Transition`
> and the two comment commands only; a commit of mixed changes with no command is a plain
> `Activity`. Where the layer table or the capabilities below say otherwise, design.md PD-1 holds.

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

- **DEC-12** (developer, 2026-11-13: "proceed with the thin option"): a command carries its data
  (an `Add` or `Replace` its triples, an extension its parameters); a stored activity record and a
  published message carry references only: who, when, the use case, its small parameters, and the
  IRI, class and version token of each generation and invalidation, never the aggregate's triples.
  An observer that needs the content reads it (`get_graph`). Undo and version history are not
  planned (developer, 2026-11-13); the version tokens in the records are what a later version
  history would resolve.

- **DEC-13** (developer, 2026-11-13, "accept all recommendations"): DEC-10 and DEC-11 confirmed.
  Activity records are kept when their resource is deleted; the collaboration EPIC's transition
  records follow this once adopted (first Rabbit-hole, now decided). Personal data in records (the
  principal) is accepted for now; a purge per principal comes when a consumer needs erasure.
  Observers run right after the commit, inside the same request (the book's way); slow work goes to
  the broker. No route to read an aggregate's history in this EPIC.

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

## Where the PLAN and the code differ from the shape (reconciled 2026-11-14)

The developer asked (2026-11-14) to reconcile the shape with what is planned and built. The text
above stays as shaped; this table says where the PLAN (design.md) or the code departs from it or
adds to it. Every DEC holds. "Built" means merged or in an open PR; "planned" means gated in the
PLAN and not built yet. At the archive this table becomes the "As built" record.

| Above | Now | Decision | State |
|---|---|---|---|
| Appetite; layer table: files (`Upload`, `DeleteFile`), collaboration (`Comment`, `Reply`, `Transition`, `AddMember`, `RemoveMember`), access (`Grant`, `Revoke`, `Prohibit`) | Layer 2 is `Transition`, `PostComment`, `PostReply is_a: PostComment` and `DeleteFile`. The toolkit has no add-member, remove-member or upload operation; grants are one "set grants" call on the system database (a No-go); `Comment` and `Grant` are stored classes already | PD-1 | `Transition` built (stage 2); `PostComment`, `PostReply` and `DeleteFile` built (stage 4) |
| Layer table: the handler of layers 1 and 2 is "the toolkit" | Toolkit handlers for `Transition`, `PostComment` and `PostReply` only. `Add`, `Replace`, `Remove` and `DeleteFile` are recorded and observed, with no handler; a consumer handler writes through the unit of work (for files, `remove_with_files`, which with no mapper records a plain `Remove`) | PD-1, PD-15 | built (stages 3, 4) |
| Layer table / PD-15: `command=` comes with the bus | `Collaboration.transition` already takes `command=` (a `Transition` or a subclass): its states, comment and `used_resource` are overwritten, its other slots stored, so a consumer can store a subclass with its own slots with no bus. `transitions` returns every record as a plain `Transition`, so a subclass's own slots are not read back | PD-11, PD-15 | built (stage 2); `comment(command=)` built (stage 4): `comment` and `transition` record the command only when it is passed; other calls, such as `delete_cascade`, record a standard activity |
| Solution outline: `bootstrap(uow=...)`; `bus.handle(PublishRelease(...))` | `bootstrap(mapper=..., commands=..., observers=..., limit=..., **dependencies)`; `bus.handle(command, collaboration)`; a handler and an observer get `(activity, work)`, where `work` gives the session, the collaboration, a unit of work and `send`; `command(cls, ...)` builds a command with its id. `bootstrap` adds the toolkit handlers a consumer does not replace and refuses with `ValueError` a dependency no handler or observer names, and a parameter after `(command, work)` with no default and no dependency (`commands`, `observers`, `limit` and `mapper` are `bootstrap`'s own names, so cannot be dependencies; `*args` and `**kwargs` take none); past the limit `handle` logs and raises `MessageLimitExceeded`; `handle` returns the handler's result; `send` on a finished run is a `RuntimeError` | PD-13, PD-14 | built (stage 3) |
| Solution outline: `used_resource=[m1, m2]` | `used_resource` is one IRI; a use case over several aggregates declares a slot of its own | PD-2 | built (stage 1) |
| DEC-1: generations and invalidations "each linked to its activity" | Linked both ways (`rp:generation` / `rp:invalidation` from the activity, `prov:activity` back). The entity, its class and its version token are `rp:entity`, `rp:entityClass` (absent for a root with no type; for a root of several types, the first in sorted order) and `rp:entityVersion`: PROV-O has no property from a generation to its entity. A stored activity is typed with its class and every ancestor up to `prov:Activity` | PD-3 | built (stage 1) |
| DEC-2: one message per commit | Holds. Also: a commit with no command whose changes are of more than one kind is a plain `Activity`; the message is the generated model of the stored record | PD-1, PD-4, PD-7 | built (stages 1, 2) |
| DEC-2: one message per commit | A batched commit is one commit per batch: one activity and one message each; a failure leaves the records of the batches that committed | PD-8 | built (stage 2) |
| DEC-3: "once committed, the same class is the stored record" | Holds, and so one command is recorded by one commit: a second commit with it is an error. An activity IRI that already exists refuses the commit. A `Served` is claimed when a transaction sends its request: a refused commit spends it, an empty one does not. The unit of work takes the command's `Served` (`UnitOfWork(served=)`) and a batched commit with one is refused | PD-8, PD-16, D-10 b | one `Served` one commit and the id guard built (stage 2); `UnitOfWork(served=)` and the batch refusal built (stage 3) |
| DEC-3: once committed (not said: a commit with no change) | A transaction with no change sends nothing: no activity, no message; a `Served` given to it is not spent | PD-8, D-10 b | built (stages 2, 3) |
| DEC-5: an observer's error is logged | Holds. Also: commands an observer sends are queued and run after the current one, with the collaboration they were sent under; a queued command's error is logged and the queue goes on; if the handler then raises, the queued commands are dropped and the commit and its publish stand; an observer's own commits are recorded as standard activities; each observer of a commit gets its own copy of the activity; an observer of a commit made outside `bus.handle` (a generic route) cannot send a command | PD-13, D-10 c | built (stage 3) |
| DEC-6: the session records on every commit and hands the activity to the bus | Holds through a hook on the session (`Session(on_commit=)`). Sessions on the system database record nothing (No-gos); the application database's sessions record like a tenant's; `load_graph` before its commit, the sweeps and restore's import are not commits and record nothing. The kit holds an optional `kit.bus`, set after the kit is built (`kit.bus = bootstrap(mapper=kit.mapper, ...)`) or by `install_service(bus=)`, whose bus must be built with the kit's mapper; with none, commits are recorded and nothing is published; only tenant and application sessions get the hook | PD-9, PD-10, PD-17 | recording and the session hook built (stage 2); the kit passing the hook and `kit.bus` built (stage 3) |
| DEC-6: the session records the standard activity on every commit | A session can be opened with `record_activities=False` (`open_session`, `fake_session`): it records nothing and guards no activity IRI, and its hook, if any, still gets each commit's activity. The tenancy passes `False` only for the system database; the PLAN uses it to measure the cost | PD-9, PD-12 | built (stage 2) |
| DEC-7: "the generator checks the direction … and refuses a consumer-set value for the slots the toolkit fills" | The direction is checked per class (`activity_direction`: a stored class's slot may not range over a consumer activity class that is no aggregate root); the ownership rule no longer reports a class that descends from `Activity`. The generator refuses (`toolkit_filled`) a consumer `slot_usage`, `ifabsent` or attribute on a toolkit-filled slot, a slot whose expanded `slot_uri` is that of one, and a required payload slot; a value set at run time is refused by the bus. In the toy the sibling module is imported by the aggregator schema, which declares no stored class | PD-20, PD-21, D-11 e | built (stage 3) |
| DEC-7: the slots the toolkit fills are "start, end, principal" | Also the generations and invalidations, and for a transition its two states and its comment. The two state slots are shared with `Comment`, so they are toolkit-filled there too (the check refuses a consumer `slot_usage` on them in a `Comment` subclass) | PD-2, PD-11 | built (stages 1, 2, 3) |
| DEC-10: "one provenance graph per tenant" | `{tenant}/provenance`, a template of the IRI policy like the registry's; the graph is not registered, so no listing, referrer or sweep query sees it; a restore accepts it. A restore rewrites the entity IRIs and keeps the activity IRIs, so the original and the restored tenant hold records of the same IRI; the restore itself records nothing. An activity's IRI is `urn:uuid:<uuid4>`. `provenance` is now a reserved word of the IRI layout | PD-3, PD-5 | built (stage 1) |
| DEC-12: records carry references only | Holds. Slots a command carries and a record does not are marked `payload` in the command class and are never required there. The record keeps a command's other slots for as long as the tenant exists, so free text and personal data belong in `payload` slots | PD-2, PD-8 | built for `Transition` (stage 2); the bus's use built (stage 3) |
| DEC-2, DEC-9: what is published | What is published is recorded, with two exceptions: a commit that applied but whose every graph another writer overwrote before the confirmation raises the false `Conflict` of atomic-commit PD-4 and is recorded, not published; a session opened with `record_activities=False` and a hook publishes activities it does not record. A commit that applied and was overtaken in part publishes when its activity is stored; a remove of a root another writer removed first succeeds, records nothing and publishes nothing | D-5 a, D-6 a | built (stage 2) |
| DEC-3: a command is the request (not said: who may build its record) | A command's record (`Served`) may only carry statements about its own activity and about blank nodes, never a type or a slot the session fills, nor a class the schema does not have; its IRI is a `urn:uuid:` UUID. It serves one commit and is spent by a refused or an empty one; a session that neither records nor has a hook refuses it. Code that holds a session and builds a `Served` is trusted for the other slots | D-5 b, D-6 b, f | built (stage 2) |
| DEC-13: transition records are kept on delete | Holds. `transitions` returns only activities that used the aggregate and generated a version of it, each with only the parts about it, and a consumer's subclass comes back as a plain `Transition`. Its consequences: no call of a collaboration returns the transitions of an aggregate that is no longer stored (`NotFound`); the session's own read `Session.activities` checks no access, like every session read, and returns any activity of the provenance graph, of a deleted aggregate too; an aggregate added again at the same IRI shows the old history; a kept record may name a comment that is gone. Comments are still deleted with their target, with no invalidation each. Stored `rp:TransitionRecord` graphs of a consumer on `develop` are not migrated: they stay registered aggregates the toolkit no longer reads, `referrers` of their aggregate lists them under the class IRI `rp:TransitionRecord`, and a remove of their aggregate no longer drops them (a session removes each like any aggregate) | PD-1, PD-11 | built (stage 2) |
| Rabbit-holes, "The exact PROV shape": a round-trip test | Done for `Add`, `Replace`, `Remove`, a bare `Activity` and a consumer subclass (TC-105). A framed activity carries `entity_class` as a compact IRI when the context has its prefix, as every framed IRI slot does; nothing in this EPIC reads an activity through a frame | PD-4, PD-24 | built for the toolkit classes (stage 1); a consumer subclass built (stage 3) |
| Rabbit-holes, "Commit cost": measured in the PLAN | Measured on Fuseki in stage 2, printed and not asserted. A single replace against 20 000 stored activities: 179.7 ms recorded and 186.4 ms unrecorded per commit in one run, 106.8 ms and 110.6 ms in a second (200 commits each): no cost above the noise between runs. A commit of 500 new books: 4.1 s and one request of about 3.65 MB (3.8 to 4.0 s and about 2.9 MB before): about a quarter more to send, about the same time | PD-12 | built (stage 2) |
| No-gos: tenancy activities | `Tenancy.create` records the `Add` of the tenant root in the tenant's provenance graph, associated with the creator, so every new tenant starts with one activity; the access record (system database) is not recorded | PD-9 | built (stage 2) |
| Rabbit-holes, "Loops": cap the messages one `handle` call processes | The limit is 100 commands by default; an observer that commits in a loop is bounded by the same number, inside `handle` or outside it. `handle` logs `MessageLimitExceeded` at error level before it raises it. A `handle` that an observer calls itself joins the count; past the limit its error is logged by the commit's hook, not raised to the outer caller | PD-13, D-10 a, D-11 c | built (stage 3) |
| Rabbit-holes, "Hidden aggregates": observers run with the toolkit's rights | An observer gets the session that committed (the caller's principal), and a session checks no access: it has that session's full reach in the database, not only what the caller could do. Inside `handle` it gets the caller's collaboration only for a commit of that collaboration's session; otherwise `work.collaboration` is None. Anything beyond the aggregates the activity names is checked through the collaboration or `kit.require`. What it commits is recorded as the caller's activity | PD-13, PD-17, D-11 a | built (stage 3) |
| Observers: (not said) | An observer's `work.collaboration` belongs to its own commit only; for a commit made on another session it is None and `work.send` raises `RuntimeError`, which is logged as that observer's error. A command runs with the collaboration it was sent under | D-11 a | built (stage 3) |
| Wiring: (not said) | `bootstrap` checks every handler and observer parameter when the bus is built, so a typo or one of its own four names fails at start, not at the first message | D-10 d, D-11 d | built (stage 3) |
| What Changes: `rp_provenance.yaml` holds the layer 1 and 2 classes | Layer 1 and the events are there; each layer-2 class lives in its feature's module (`rp_workflow.yaml`, `rp_discussion.yaml`, `rp_files.yaml`) | PD-11, PD-18, PD-19 | layer 1 built (stage 1); `Transition` built (stage 2); `PostComment`, `PostReply` and `DeleteFile` built (stage 4) |
| What Changes: `services/session.py` records the activity | The shape is in a new `services/provenance.py`; the session calls it. An import contract keeps both free of the mapper | D-3 b | built (stage 1) |
| What Changes: "`UnitOfWork` takes the command it serves" | It takes the command's `Served` (the model, its own triples, its class IRIs), which the mapper builds | PD-8, PD-16 | `Served` built (stage 2); the unit of work built (stage 3) |
| What Changes: testkit "a recording observer and a fake bus" | A recording observer only (`RecordingObserver`, `testkit/messages.py`): the bus is in process with no I/O, so a consumer test uses the real one | PD-22 | built (stage 4) |
| What Changes: docs in `howto/adopt.adoc` | A new `howto/event-driven.adoc`, linked from `adopt.adoc`; `adopt.adoc` has the upgrading note | D-3 f | built (stage 4): the note and the page |
| Capabilities: "None as deltas here" | Four modified: `rp-workflow` and `rp-reverse-references` (records kept), `rp-iri-policy` (the provenance graph), `rp-generation` (activity classes are exempt from the ownership rule; the direction and toolkit-filled rules) | PD-5, PD-11, D-3 e | deltas written |
| Impact: (not said) | Breaking for a consumer on `develop`: `TransitionRecord` becomes `Transition` in the public API; every commit on the fake store now also writes a provenance graph; five frames appear in a generated folder | PD-11, RISK-9 | built (stages 1, 2) |
| Impact: (not said) | The toolkit's own schema is at version "2": removing the class `rp:TransitionRecord` met the schema lock that `schema-migrations` merged the same day. Its migration `1__2.yaml` has no steps, because stored transition records are not migrated | PD-1, D-7 | built (stage 2) |
| Impact: "more triples per commit" | Also one more reading of the session clock per commit, for the activity's end. A test clock that counts its readings sees the tracking time one reading earlier than the last | PD-7 | built (stage 2) |
