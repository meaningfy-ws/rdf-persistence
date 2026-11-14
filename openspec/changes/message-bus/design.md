> Derives from: EPIC `message-bus` (proposal.md, DEC-1 to DEC-13; inputs/seed.md, "Question round
> of the epic session"). Decisions here are `PD-n`; delivery decisions are `D-n`.
> Type: Implementation (design).

## Context

What `develop` does today (read 2026-11-14):

- Every write to a tenant database goes through `Transaction.commit` (`services/session.py`): one
  update request made of a guard operation that inserts a commit marker, the marked operations of
  each change, and a release. A request whose guard fails changes nothing. The exceptions are
  `Session.load_graph` (a marker and a `put_graph`), restore's `import_quads` and the sweeps.
- Every session of the service is built in one place, `Tenancy._session`; sessions on the system
  database (access records, grants) use the same class.
- A transition (`services/transitions.py`) writes a `TransitionRecord` as its own aggregate (graph,
  registry entry, path `rp-transitions`) in the transaction that changes the state. A remove drops
  it with its aggregate through `_DROP_DEPENDENTS` (the `(rp:TransitionRecord, prov:used)` pair the
  kit composes), as it drops comments. `Collaboration.transitions` reads the records with
  `Session.graphs_with(prov:used, iri)`.
- `Activity` (`rp_provenance.yaml`) has `id` and `was_associated_with` only. `Comment` and `Grant`
  are stored model classes. The mapper types a subject with its own class only and reads a graph
  as the class the caller names; it has no dispatch by `rdf:type`.
- A tenant has three graphs outside its aggregates: `meta`, `registry` and the loaded graphs. The
  tenant sweep only looks at loaded graphs; a dump exports every quad; restore refuses a graph the
  IRI policy does not mint (`domain/tenant_move.py`, `check_graphs`).
- `TransitionRecord` is in no release (v0.2.0 predates it).

## Goals / Non-Goals

**Goals:** one activity record per commit, in the commit's request; the fixed PROV shape, proven by
a round trip; `TransitionRecord` becomes the layer-2 `Transition`, kept on delete; the cost per
commit measured; an in-process bus with hierarchy dispatch; the generator checks of DEC-7.

**Non-Goals:** the proposal's No-gos; `AddMember`, `RemoveMember`, `Upload`, `Grant`, `Revoke`,
`Prohibit` (PD-1); handlers for layer 1 (PD-1); a migration of stored `rp:TransitionRecord` graphs
(PD-1); a fake bus in the testkit (PD-22); a route or call that reads the history of a deleted
aggregate (DEC-13).

## Decisions

### From the question round (developer, 2026-11-14)

- **PD-1** The seven answers in inputs/seed.md hold as decisions: (1) layer 2 here is `Transition`,
  `PostComment`, `PostReply`, `DeleteFile`; (2) toolkit handlers for `Transition`, `PostComment` and
  `PostReply` only; (3) the names `PostComment` and `PostReply is_a: PostComment`; (4) no migration;
  (5) a mixed commit with no command is a plain `Activity`; (6) comments are still deleted with their
  target, with no invalidation each; (7) the PROV shape of PD-3. This narrows the layer table of
  the proposal; the proposal carries a dated note.

### The model and the shape (stage 1)

- **PD-2 Classes** (DEC-8). In `rp_provenance.yaml`:
  - `Activity` gains the optional slots `started_at_time` (`prov:startedAtTime`), `ended_at_time`
    (`prov:endedAtTime`), `generations` (`rp:generation`) and `invalidations` (`rp:invalidation`).
    The last two are multivalued, range `Generation` / `Invalidation`, `inlined_as_list`, annotated
    `owned: true`.
  - `Generation` (`class_uri: prov:Generation`) and `Invalidation` (`prov:Invalidation`), no
    identifier slot, with the required slots `activity` (`prov:activity`, range `uri`), `at_time`
    (`prov:atTime`, datetime), `entity` (`rp:entity`, uri) and `entity_version`
    (`rp:entityVersion`, string), and the optional `entity_class` (`rp:entityClass`, uri: the
    session accepts a root with no `rdf:type`). The existing `version` slot is not reused: it
    is annotated bookkeeping and the mapper skips it.
  - `Add`, `Replace`, `Remove`: `is_a: Activity`, `class_uri` `rp:Add`, `rp:Replace`, `rp:Remove`.
  - `used_resource` and `started_at_time` move here from `rp_workflow.yaml` (same `slot_uri`,
    `used_resource` no longer required globally). `used_resource` stays single-valued: making it
    a list would change `Transition.used_resource` for every caller; a use case over several
    aggregates declares its own slot (the proposal's outline is an illustration).
  - The slots the toolkit fills carry the annotation `toolkit_filled: true`: in stage 1
    `started_at_time`, `ended_at_time`, `was_associated_with`, `generations`, `invalidations`;
    from stage 2 also `from_state_iri`, `to_state_iri`, `transition_comment` (PD-11). Slots a
    command carries but a record does not (DEC-12) carry `payload: true`; a payload slot is never
    required in its command class (the message drops it).
  - Where the annotations sit: `toolkit_filled` on the slot definition; `payload` in the
    **command class's `slot_usage`**, never on the slot definition (`to_state` and `body_value`
    are stored, required slots of other classes), and it is read from the induced slot of the
    command's class. Both are declared in the `RpAnnotation` enum (`rdf_persistence/model/rp_core.yaml`)
    and in `generation/checks/hard.py` `ALLOWED_ANNOTATIONS` (boolean).
  - `services/vocabulary.py` gains `TOOLKIT_FILLED`, the names of the metamodel slots annotated
    `toolkit_filled`, read from `metamodel()`, and `SESSION_FILLED`, the five the session itself
    writes (a literal tuple; a test pins it as a subset of `TOOLKIT_FILLED`). A slot is "set" when
    it is not None and not an empty list.
  - `rp_provenance` (and, in stage 4, `rp_files`) join the generated-model sets the mapper reads
    (`entrypoints/kit.py` and `tests/toy.py` `MODULES`); without them a `Generation` cannot be
    read back.
- **PD-3 The stored shape** (DEC-1, DEC-10, DEC-12), for a replace of one book:

  ```turtle
  GRAPH <tenant>/provenance {
    <urn:uuid:A> a rp:Replace, prov:Activity ;
        prov:startedAtTime "…"^^xsd:dateTime ; prov:endedAtTime "…"^^xsd:dateTime ;
        prov:wasAssociatedWith <principal> ;
        rp:generation <tenant>/provenance/.well-known/genid/1 ;
        rp:invalidation <tenant>/provenance/.well-known/genid/2 .
    <…/genid/1> a prov:Generation ; prov:activity <urn:uuid:A> ; prov:atTime "…" ;
        rp:entity <book> ; rp:entityClass <Book> ; rp:entityVersion "new token" .
    <…/genid/2> a prov:Invalidation ; prov:activity <urn:uuid:A> ; prov:atTime "…" ;
        rp:entity <book> ; rp:entityClass <Book> ; rp:entityVersion "old token" .
  }
  ```

  - An activity is typed with its own class **and every ancestor class** up to `prov:Activity`
    (so `ApproveBook` is also `rp:Transition`). The session cannot know a consumer's subclasses,
    and a read by `rp:Transition` must find them; a plain PROV query finds every activity.
  - Add: one generation. Replace: one generation (new token) and one invalidation (old token).
    Remove: one invalidation (the token it was removed at). `prov:atTime` is the activity's end.
  - `rp:entityClass` is the class IRI of the root (several types: the first in sorted order; none:
    no triple). A generation takes it from the triples the commit writes. An invalidation takes it
    from the stored graph: `Session._stored` is widened to return the root's types with the version
    it already reads (no extra request), so a replace that changes the class invalidates the old
    class and generates the new one.
  - The parts are blank nodes, skolemised under the provenance graph by the existing
    `_skolemised`. `rp:entity`, `rp:entityClass`, `rp:entityVersion`, `rp:generation`,
    `rp:invalidation` are ours because PROV-O has no property from a generation to its entity.
  - The activity's IRI is `urn:uuid:<uuid4>`, like the commit marker's: no IRI template, nothing
    to rewrite on restore. `Activity.id` is required in the generated model, so a command needs one
    when it is built: `messagebus.command(cls, **slots)` mints it (stage 3). A `Served` whose id
    does not start with `urn:uuid:` is a `ValueError` (an aggregate IRI as an activity id would be
    rewritten on restore).
- **PD-4 The message** (DEC-2, DEC-12) is the generated model of the stored record: the activity's
  class with the `SESSION_FILLED` slots set, the other toolkit-filled slots as its caller set them,
  and no payload slot. The round-trip test (task 1.3)
  proves, for one `Replace` and for one consumer subclass: model → mapper triples equals the
  session's triples minus the ancestor types other than the activity's own class; model → JSON (`model_dump(mode="json")`) → JSON-LD
  expansion with the generated context → the same graph; that graph framed and compacted → the same
  model. Parts are compared without order, by `(entity, entity_version)`: the mapper reads
  multivalued values sorted by node, and the nodes are random. The generator therefore emits a
  frame for `Activity` and each descendant in a target's import closure, the toolkit's classes
  included, in the metamodel and in every consumer target (today only roots get one).
- **PD-5 The provenance graph** (DEC-10). `IriPolicy` gains `provenance_template`, default
  `{tenant}/provenance`; `Iris.provenance(tenant)`; `_require_distinct_graphs` probes it as the
  fourth graph; `check_graphs` accepts it on restore. The graph is not registered (like `meta`),
  so no listing, referrer, key or sweep query sees it (they all join the registry; the two
  free scans look for `rp:fileKey`, which no record carries). The IRI policy guard compares the
  recorded policy with the configured one: a recorded policy from before this change has no
  `provenance_template` and SHALL read as the default, not as a change (task 1.2, TC-07).

### The activity on every commit (stage 2)

- **PD-6 One more marked operation** (DEC-9). `Transaction.commit` appends
  `INSERT { GRAPH $provenance { $triples } } WHERE { <marked> }` before the release, so a refused
  commit records nothing by the mechanism that already makes it write nothing. The triples are
  built in `services/provenance.py` (D-3 b; the session imports it) from vocabulary constants, like `registry_triples` and
  `commit_marker_triples` (the session has no mapper and `mapper.py` imports it); task 1.3's
  round trip pins them against the mapper.
- **PD-7 What the session fills.** Start: the transaction's marker time. End and every
  `prov:atTime`: the session clock when `commit` builds the request. Principal:
  `session.principal`. The class when no command is served: `Add`, `Replace` or `Remove` when every
  change is of that kind, else `Activity` (PD-1 item 5).
- **PD-8 A served command.** `Session.transaction(served=None)` takes a
  `Served(activity, triples, types)`: the command's model with its `id` and without its payload
  slots (set to None), its own triples, and its class IRIs (own and ancestors).
  `Mapper.served(command)` builds it: `triples` are the mapper's triples of the command without
  the `rdf:type`, the payload slots (found by annotation on the induced slots) and the
  `SESSION_FILLED` slots. The other toolkit-filled slots stay in `triples`: their caller
  (`Transitions._store`) has set them. The session adds the types and what it fills.
  - The request gains the guard `FILTER NOT EXISTS { GRAPH $provenance { <id> ?p ?o } }`: an
    activity IRI that exists refuses the commit as a `Conflict` naming it. A forged or reused id
    can therefore never merge into an existing record.
  - **One command, one commit.** A `Served` serves one commit: a second transaction given the same
    `Served` raises `RuntimeError` before anything is sent; `UnitOfWork.commit(batches=True)` with a
    command raises `ValueError` (several commits, one record). A handler that needs a second commit
    makes it unserved (through `work.session`; it is recorded as a standard activity) or sends a
    second command.
  - `Session.add_graph`, `replace_graph` and `remove` take `served=None` too and pass it to their
    one-change transaction.
  - As built (task 2.2): a `Served` is claimed when its transaction opens, so a refused or failed
    commit spends it too; a retry builds a new `Served` (`mapper.served(command)` again). `Served`
    is a plain class and the events are tuples, because the model guard forbids dataclasses in
    `services` and they are internal to one commit, never stored or sent as such.
  - Diagnosis after a failed confirmation (`_diagnose`): the existing reasons first, unchanged. Only
    when they find none and the commit was served, an `ASK` for the activity IRI in the provenance
    graph; if it is there, `Conflict` naming it. (A served commit that applied and whose every graph
    was overwritten is the documented false conflict; it then names the activity IRI, which is
    true: the record exists.)
- **PD-9 Which sessions record.** `Session(record_activities=True)` by default, also for a session
  a consumer opens with `open_session`. `Tenancy._session` passes `False` when `database == self._system`
  (No-gos: tenancy activities). The tenant root's writes in the tenant database are recorded like any
  commit, with the principal of the session that makes them (the creator for `Tenancy.create`). `load_graph`, the sweeps and restore's import are not commits and record
  nothing; the commit that registers a loaded graph records its add or replace.
  The application database (`app-level-data`, merged 2026-11-14) is no system database: its
  sessions record, in `iris.provenance(iris.application)`, and get the `on_commit` hook like a
  tenant's (the session's `tenant_iri` is the application IRI, so nothing special is needed).
- **PD-10 After the commit** (DEC-6, DEC-9). `Session(on_commit=None)`: after the confirming `ASK`
  holds, `commit` builds the message (PD-4) and awaits `on_commit(activity, session)`. An exception
  from it is logged and swallowed: the commit stands. No hook: nothing is built.
  - Logging, here and in the bus: `log = logging.getLogger(__name__)` as the other services do, and
    `log.exception(...)`. The hook: `"on_commit failed on <activity id>"`. An observer:
    `"<observer qualified name> failed on <activity id>"`. A queued command:
    `"<command class> <command id> failed in the queue"`.
- **PD-11 `Transition`** (DEC-13 replaces PD-15 of
  `openspec/changes/archive/2026-11-14-collaboration-and-reference-collections/design.md`). In `rp_workflow.yaml`
  `TransitionRecord` becomes `Transition`: `is_a: Activity`, `class_uri: rp:Transition`, no
  `AggregateRoot` mixin, no `rp_path`; slots `used_resource` (required), `from_state_iri`,
  `to_state_iri`, `transition_comment` (annotated `toolkit_filled`, optional in the class so the
  command can be built), and the payload slots `to_state`, `expected_version` (new, string, defined
  in `rp_workflow.yaml`) and `body_value`. `Transitions._store` takes the command if one is given
  (else a fresh `Transition`), sets the three computed slots with `model_copy(update=…)`, and only
  then asks `mapper.served`. A command that arrives through the bus with one of them set is
  refused there (PD-13); a direct caller's value is overwritten.
  `Transitions._store` passes the record as the `Served` of the transaction that replaces the
  aggregate and adds the comment; it no longer adds a graph for the record. So a transition's
  activity is one `Transition` with a generation and an invalidation of the aggregate and, with a
  comment, a generation of the comment.
  - `Transitions.transitions(iri)` reads through a new `Session.activities(type_iri, predicate,
    obj)`: the subjects of the provenance graph typed `type_iri` with that statement, each with
    its parts, as one graph per activity; decoded as `Transition` (a subclass comes back as its
    parent, the mapper's documented shortcut), oldest first, ties by IRI. It first reads the
    aggregate (`Session.get_graph`), so an aggregate that is not stored is `NotFound`: the access
    check alone reads no store.
  - The `(rp:TransitionRecord, prov:used)` dependents pair and `transitions.dependents` are
    deleted. Comments keep theirs.
  - Consequences, stated in the docs and the spec deltas: the records of a removed aggregate stay
    in the provenance graph and no call returns them (`transitions` needs `read` on a stored
    aggregate); an aggregate added again at the same IRI by code that holds a session shows the
    old history; a kept record may name a comment that was deleted with the aggregate.
  - Public API: `TransitionRecord` is replaced by `Transition` in `rdf_persistence.__all__`.
- **PD-12 Cost** (the Commit cost rabbit-hole). Measured on Fuseki, printed and recorded, not
  asserted: (a) atomic-commit's IT-06
  (`tests/integration/store/test_transaction.py::test_it06_a_commit_of_the_default_limit_of_new_books_is_one_update_within_30_s`;
  500 books in one commit; 3.8 to 4.0 s before) re-run; (b) a
  new slow container test: 200 single replaces in sequence against a provenance graph already
  holding 20 000 activities, mean time per commit, beside the same run on a session with
  `record_activities=False`. The figures go to the durations table and to the proposal's "As
  built". A mean above twice the unrecorded one goes to the developer before stage 2 merges.

### The bus (stage 3)

- **PD-13 `services/messagebus.py`** (DEC-5, DEC-11), about one screen:
  - `MessageBus(commands: Mapping[type[Activity], Handler], observers: Mapping[type[Activity],
    Sequence[Observer]], *, limit: int = 100)`. A key that is not an `Activity` subclass, or a
    `limit` below 1, is a `ValueError` at construction.
  - `Handler = Callable[[Activity, Work], Awaitable[object]]`;
    `Observer = Callable[[Activity, Work], Awaitable[None]]`.
  - `await bus.handle(command, collaboration)` returns the handler's result. It refuses with
    `InvalidBody` a command with a toolkit-filled slot set (before the handler runs), finds the
    handler of the first class in `type(command).__mro__` that has one, else raises
    `LookupError("no handler for <class name>")`. `MessageLimitExceeded`'s message is
    `"message limit <limit> reached"`. The handler's exception reaches the caller.
  - `await bus.publish(activity, session)` is the session's `on_commit`. It calls the observers of
    each class in the activity's `__mro__`, nearest class first, in registration order; each
    exception is logged with the observer's name and the rest still run.
  - The bus takes `mapper=None` at construction (`bootstrap(mapper=kit.mapper)`). `Collaboration`
    exposes `session` and `mapper` as read-only properties.
  - `Work` is what a handler or an observer gets: `work.session`; `work.collaboration` (None for a
    commit made outside `handle`); `work.unit_of_work()`, a `UnitOfWork` on the session with the
    bus's mapper (`RuntimeError` if the bus has none); `await work.send(command)`, which queues a
    command. A **handler's** `Work` serves its command: `handle` builds the command's `Served`
    once (`mapper.served`), and every `unit_of_work()` of that `Work` gets that same object, so a
    second commit with it raises the `RuntimeError` of PD-8. (A bus without a mapper builds none.)
    An **observer's** `Work` serves none: what an observer commits is recorded as a standard
    activity (the command it observes is already committed, PD-8).
  - `command(cls, **slots)` builds a command with a fresh `urn:uuid:` id.
  - `handle` runs the queue after the current command, first in first out, each queued command
    through the same refusal and dispatch, with the same collaboration. A queued command's error
    is logged and the queue goes on (the caller's own command already succeeded). `handle` keeps
    the current `Work` in a `ContextVar`, so a commit made inside it publishes with that `Work`.
  - Inside `handle` the limit counts the commands that call starts (the first and every queued
    one); starting one more raises `MessageLimitExceeded` (new, in `domain/exceptions.py`) naming
    the limit, from `handle` to its caller, and the rest of the queue is dropped. A `handle` called
    while another is running in the same context (an observer or handler that calls `bus.handle`
    itself) joins the running call's count.
  - Outside `handle`, `publish` counts its own nesting in a `ContextVar` (an observer that commits
    on the session it was given publishes again); past the limit `publish` raises
    `MessageLimitExceeded`, which the session's hook logs (PD-10), and the loop ends there.
  - `work.send` outside `handle` (a generic route's commit) raises `RuntimeError`: there is no
    caller's collaboration to run a command with. It is logged as that observer's error. Stated in
    the how-to as a limit.
- **PD-14 `bootstrap`** (DEC-11): `bootstrap(*, commands=None, observers=None, limit=100,
  **dependencies) -> MessageBus`. It adds the toolkit handlers of PD-15 unless `commands` names
  the class, and wraps each handler and observer in `functools.partial` with the dependencies its
  signature names. A dependency no handler names is a `ValueError` (a typo would otherwise pass).
- **PD-15 The toolkit handlers** call the collaboration: `Transition` →
  `collaboration.transition(used_resource, to_state, if_version=expected_version,
  comment=body_value, command=command)`; `PostComment` / `PostReply` (stage 4) →
  `collaboration.comment(used_resource, body_value, audience=comment_audience or (),
  references=comment_references or (), reply_to=replies_to (None for a `PostComment`),
  command=command)`. `Collaboration.transition` and `comment` gain the keyword `command`, which
  they pass to `_store` (PD-11), where the `Served` is built after the computed slots are set (the
  `Served` that `handle` built is not used by the toolkit handlers), so an `ApproveBook` is stored
  as an `ApproveBook`. Without it they build
  the standard activity themselves, so they work with no bus.
- **PD-16 `UnitOfWork(session, mapper, ..., served=None)`**: `_write` passes that `Served` to the
  transaction. A caller without a bus builds it with `mapper.served(command)`.
- **PD-17 The kit.** `kit.bus` is an attribute, None at first and assignable (a handler's
  dependencies are often parts of the kit, so the bus is built after it); `install_service(bus=None)`
  sets it. `Tenancy(..., on_commit=None)`: the kit passes a method of its own that awaits
  `self.bus.publish(activity, session)` if `self.bus` is set when the commit happens;
  `Tenancy._session` gives it to tenant-database sessions (not to the system database's).
  `FakeSession`/`fake_session` of the testkit take `on_commit` too.

### Layer 2, the checks, the toy (stage 4)

- **PD-18 `PostComment`, `PostReply`** in `rp_discussion.yaml` (which now imports
  `rp_provenance`): `PostComment is_a: Activity` with `used_resource` (required: the target) and
  the slots `body_value`, `comment_audience`, `comment_references`, each `payload: true` and not
  required in `PostComment`'s `slot_usage`;
  `PostReply is_a: PostComment` with `replies_to` (required, stored). `Discussion._store` serves
  one of them; its activity has one generation, the comment's.
- **PD-19 `DeleteFile`** in `rp_files.yaml` (imports `rp_provenance`): `is_a: Remove`, slot
  `used_resource`. `file_removal.remove_with_files` builds it with the mapper the kit passes and
  gives its `Served` to `session.remove(iri, if_version, served=…)`. No handler (PD-1).
- **PD-20 The generator checks** (DEC-7; P-0001):
  - The ownership rule no longer reports a consumer class that descends from `Activity`.
  - New `BoundaryRule.activity_direction`: a slot of a consumer class that does not descend from
    `Activity` SHALL NOT range over a consumer class that descends from it and is not an aggregate
    root (a stored root that `is_a: Activity` is a modelling choice of today and stays allowed). Ranging over a toolkit activity
    class (`Activity`, `Transition`) stays allowed (`was_generated_by`).
  - New `HardRule.toolkit_filled`: a consumer class SHALL NOT give `slot_usage`, `ifabsent` or an
    attribute of its own for a slot annotated `toolkit_filled`, and SHALL NOT have an induced slot
    that is both `payload` and required.
  - Each has a planted-fault row in the check tables.
- **PD-21 The toy.** `tests/fixtures/library/books_activities.yaml` imports `books.yaml` and is
  imported by the aggregator `library.yaml` (which declares no stored class), so no new generation
  target: `ApproveBook is_a: Transition`; `ShelveBooks is_a: Activity` with `used_resource` and
  `shelf_note` (string). `tests/toy.py` exports both.
- **PD-22 Testkit.** `RecordingObserver` (an observer that keeps the activities it got). No fake
  bus: the real one is in process and has no I/O, so a consumer test uses it.
- **PD-23 Stage order** (from the attack, 2026-11-14). `Mapper.served` needs a class of the
  schema, so the toy's activity classes and the checks that let them generate (PD-20, PD-21) are
  built in stage 3, before the bus is wired; stage 4 keeps the comment and file commands, the
  testkit, the feature scenarios and the docs. The headings above keep the decisions by topic.
- **PD-24 A framed activity carries compact IRIs** (lead, 2026-11-14, from task 1.3). Framing
  compacts the value of an IRI slot to a CURIE when the context has a prefix for its namespace, as
  it does for every IRI slot of every framed class today; `entity_class` is the first slot whose
  value is always under a consumer prefix (`lib:Book`). The round trip of TC-13 therefore holds
  after the compact IRIs are expanded with the context, which is the same IRI in JSON-LD. Nothing
  in this EPIC reads an activity through a frame: the message is the model built by the session
  and the records are read through the mapper. Not changed here: the context generator (it would
  change every consumer's context) and `Documents.frame`. `aggregate-events` publishes the model's
  own JSON (full IRIs), not the framed form.

## Delivery decisions

- **D-1** (lead, 2026-11-14) GitNexus rates `Transaction.commit` HIGH (13 symbols; `comment`,
  `transition`, `delete_cascade` flows). The EPIC's stated purpose is to change every commit
  (proposal, Impact), which the developer accepted; delivery proceeds, and the adversarial tester
  runs right after task 2.2.
- **D-2** (lead, 2026-11-14) The PLAN was attacked by a fresh reviewer (1 blocker, 9 major and 18
  minor findings, all folded in: PD-23 and the PDs, test cases and error-matrix rows they touch)
  and then gated by another fresh reviewer: 8.4 on the first run, 9.1/10 after its eight gaps were
  closed.
- **D-3** (lead, 2026-11-14) Review of stage 1 (PR #107; L1, L2, L3 and L4+L5 as one pass; nothing
  blocking). Accepted, fixed in the stage:
  - a. `activity_triples` raises `ValueError` for an activity without a start or an end time
    (`Literal(None)` would store the text "None"), with a test (L1, L2, L4).
  - b. The activity shape moves from `services/session.py` to a new `services/provenance.py`
    (`activity_triples`, its part helper with keyword-only `link` and `kind`); the session imports
    it. Stage 2 adds the types, the id guard and the events there. `.importlinter` gains a
    contract: `services.session` and `services.provenance` never import `services.mapper` (PD-6
    was held only by an import cycle) (L3, L4).
  - c. `vocabulary.class_iri(name)` replaces the five copies of the class-IRI expression; the
    class name `Activity` has one home, `services/schema_structure.py`, beside `AGGREGATE_ROOT`,
    used by `jsonld_context.py` and `checks/boundary.py` (L3, L4, L5).
  - d. Tests: `iris.provenance(tenant)` joins `minted_graphs` in `test_tenant_move.py` (the
    negative case: another tenant's provenance graph is refused); a message on each new assert;
    TC-09 uses `v.ENTITY`; the docstring of `mapped`; a restore of a dump whose manifest has no
    `provenance_template` (L2).
  - e. Spec: a delta `specs/rp-iri-policy/spec.md` (the minted IRIs, the template list, the
    distinct-graphs rule now name the provenance graph). The proposal's "None as deltas" is
    superseded by this and the two deltas of PD-11 (L2).
  - f. Docs: `howto/adopt.adoc` (the reserved words, the distinct-graphs rule, and an "upgrading"
    note: `provenance` is a reserved class IRI type; five frames appear in a consumer's generated
    folder, so `make generate` once; a deployment whose recorded policy already uses
    `{tenant}/provenance` for another graph cannot start and has no way out but a new policy
    record), `questions.adoc`, and the description of `rp_provenance.yaml` (L2, L3, L5).
  Rejected: reading a missing `provenance_template` of a recorded policy as the configured value
  (L5 item 2): it would let a policy change pass the guard unseen; the case is documented (f).
- **D-5** (lead, 2026-11-14) The adversarial tester's run after task 2.2
  (`tests/unit/services/test_session_activity_adversarial.py`: 46 tests, 5 findings kept as strict
  xfail until fixed). All five accepted:
  - a. A transaction of removes whose root another writer removed first: nothing is written, yet
    the confirming `ASK` holds (the graph is gone) and the hook got a `Remove` that is not stored.
    Fix: a recording commit also confirms its activity (`GRAPH $provenance { <id> a prov:Activity }`
    joins the confirm patterns). When that fails the existing diagnosis decides as today (this
    case stays a success, atomic-commit PD-17e), and nothing is published: only a commit whose
    confirmation held publishes.
  - b. A `Served` built by hand could carry statements about other subjects (a past activity, an
    aggregate) and statements the session fills (a second principal, a second time). Fix: the
    `Served` constructor refuses with `ValueError` a triple whose subject is neither the activity
    IRI nor a blank node, and a triple of the activity whose predicate is `rdf:type` or one of the
    `SESSION_FILLED` predicates.
  - c. A clock that goes back gave a start after the end. Fix: the end is the later of the
    session clock and the start.
  - d. `Mapper.served` of a class the schema does not have raised `KeyError`. Fix: `ValueError`
    naming the class.
  The xfail markers are removed with the fixes.
- **D-6** (lead, 2026-11-14) Review of stage 2 (commits `c961418`, `9fccff5`; L1, L2, L3 and
  L4+L5 as one pass; nothing blocking). Accepted:
  - a. **Publish exactly what is recorded** (L4; completes D-5 a). When the confirmation fails and
    the diagnosis finds the commit applied (it returns), a recording session asks whether its
    activity is stored (`ID_TAKEN` with its id) and publishes if it is; a session that does not
    record logs a warning naming the activity and does not publish. The removes-only case of D-5 a
    finds no activity and publishes nothing. This replaces "recorded, not published" for the
    overtaken commit in the Error matrix.
  - b. **`transitions(iri)` returns only real moves of `iri`, and only what is about it** (L1).
    `Session.activities` takes an optional `entity`: only activities with a generation whose
    `rp:entity` is that IRI. `Transitions.transitions` passes the aggregate, and drops from each
    returned `Transition` the generations and invalidations of other entities, so a commit that
    also changed other aggregates does not show their IRIs to a reader of this one. The docstring
    of `Session.transaction` says a `Served` is trusted: its toolkit-filled slots other than the
    session's are stored as the caller set them.
  - c. `READ_ACTIVITIES` starts from the selective statement (`?activity $predicate $object`), then
    the type, and reads the parts with `VALUES ?link`; the comment says so (L4).
  - d. `transitions` checks the aggregate is stored with `Session.heads`, not by reading its graph
    (L5).
  - e. Activities are decoded without an aggregate's tracking graph: `Mapper.from_graph` takes
    `graph_iri: URIRef | None`, and `Transitions._decode` no longer goes through
    `discussion.decode_typed` (L3).
  - f. One home for a new activity id: `provenance.new_activity_id()`, used by `completed` and
    `Transitions._store` (and by the bus in stage 3). The id of a `Served` must parse as a UUID
    after the prefix (L1, L3).
  - g. The types of `Add`, `Replace`, `Remove` and `Activity` come from the metamodel
    (`vocabulary.activity_types(name)`, class and ancestors), not from a hand-written table; the
    tests compare with it (L5).
  - h. A `Served` given to a session that neither records nor has a hook is a `ValueError`: its
    statements would be dropped silently (L4).
  - i. The record template and the id guard's templates sit in `session.py` beside the other
    request templates, filled with `_fill_marked`; `provenance.py` builds triples and models only.
    `RECORD` in `transitions.py` is renamed (L4, L5).
  - j. Tests (L2): TC-22 asserts the provenance graph holds no statement about the book itself
    and no title; TC-24 asserts the `Add` is still there; TC-26 asserts which book is generated
    and which invalidated; TC-31 puts a change in the second transaction; TC-48 expects `Conflict`
    for the stale version and `Forbidden` for the role; one test through the toy service: a `PUT`
    of a book over HTTP records one `Replace` associated with the caller (the spec's "a generic
    replace").
  - k. Docs (L2, L4): `architecture/index.adoc` names `Session.activities`; `questions.adoc` names
    the plain activity of a mixed commit; `data-flows.adoc` and `architecture/index.adoc` say that
    the application database has its own provenance graph and that a session with
    `record_activities=False` writes none; `develop/index.adoc` says what was measured (the lead
    updates the figures after the container run); `howto/workflow.adoc` says how old
    `rp:TransitionRecord` graphs are removed (they are registered aggregates: a session removes
    each like any aggregate) and that `transitions` of an aggregate that is not stored is
    `NotFound`. The docstring of `open_session` says a hook that commits on the session it was
    given is called again for that commit (L1).
  Rejected: a shared helper for the two row-grouping loops in `session.py` (two short loops; L5
  nit); renaming locals (`done`, `record`) beyond `RECORD` (L4 nit); a test through
  `kit.application_session` instead of the tenancy method it calls in one line (L2 nit). Noted:
  `make test-perf` ran at 1.86 s of its 2.0 s budget after task 2.2 (RISK-3); stage 3 reports it
  again. Carried to stage 3: `services.messagebus` sits above `services.collaboration` in the
  `collaboration-layers` contract of `.importlinter` (L3).
- **D-4** (developer, 2026-11-14: "reconcile the deviations between epic implementation and epic
  shape") The proposal gained the table "Where the PLAN and the code differ from the shape", and
  `specs/rp-messages/spec.md` was rewritten to say what this PLAN says (mixed commits, kept
  records, the reused activity IRI, the toolkit's three handlers, the wider set of toolkit-filled
  slots, toy names instead of a consumer's). The table is kept current at each stage's merge and
  becomes the "As built" record at the archive.
  Carried to stage 2 from D-3 (task 2.2): the IRIs of a `Served` are checked where it is built (the id is
  a `urn:uuid:`, PD-3; principals come from the session), so no unchecked caller text reaches
  `URIRef` (L1); `Transition` is no aggregate root and inherits the parts as an activity, which is
  what PD-11 intends (L3). TC-16's "root frames unchanged" has one known exception:
  `TransitionRecord`'s frame gains the two part slots until stage 2 removes the class.

## Algorithm / approach

A commit, with the new parts marked `+`:

1. Changes are collected (guards, operations, confirm patterns), as today. `+` Each records what
   its event needs: root, class IRI, version read, version written.
2. `commit`: nothing collected, nothing sent, `+` no activity. `+` With `record_activities`: build
   the activity (PD-7), its triples (PD-3), the id guard (PD-8), one marked insert (PD-6).
3. One update request; the confirming `ASK`; a failed confirmation is diagnosed as today.
4. `+` With `on_commit`: build the message, await the hook, log what it raises.

**Idempotency.** A commit is not retried by the toolkit. A caller's retry of a refused commit
records one activity (the refused one recorded none). A retry after a lost response is a new
commit and conflicts on the version, as today. The id guard makes a second record under one
activity IRI impossible. An observer may run and the process stop before the next one: delivery is
at most once (DEC-11); `aggregate-events` owns durable delivery.

**Worked example** (task 3.3, TC-104 and TC-75): `bus.handle(ApproveBook(id="urn:uuid:1", used_resource=b1,
to_state="accepted", expected_version=v1), collaboration)` with observers on `Transition` and
`Activity`. The bus finds the `Transition` handler; it calls `collaboration.transition(...,
command=…)`; the commit writes `urn:uuid:1 a ex:ApproveBook, rp:Transition, prov:Activity` with a
generation and an invalidation of `b1`; `publish` calls the `Transition` observer, then the
`Activity` observer, each with an `ApproveBook` whose `to_state`, `expected_version` are None and
whose `from_state_iri`, `to_state_iri`, times, principal and events are set; `handle` returns the
new version.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Hand-write `Generation`, `Add` or a message class in Python | Change `rp_provenance.yaml`, `make generate` | LinkML is the single source (DEC-8) |
| A second request for the activity | One marked operation in the commit's request | DEC-9: all or nothing |
| Give `Session` a mapper or a schema view | Vocabulary constants in the session; `Mapper.served` outside | `mapper.py` imports `session.py`; the session stays free of schema knowledge |
| Put the aggregate's triples or a comment's text in a record | References and version tokens only | DEC-12 |
| Let an observer's error fail or undo the commit | Log it, run the rest | DEC-5 |
| Weaken a test that now sees a provenance graph | Assert the provenance graph, or compare aggregate graphs only | The record is the feature |
| Consumer terms in toolkit code or `architecture/` pages | The toy library | No-gos; `make check-docs` |
| A dict for a command or a message | The generated model | Standing rule |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| A guard fails (conflict, key conflict) | The marker is not inserted | No activity, no publish; the existing `Conflict` |
| The commit applied but the confirming `ASK` is false (another writer overwrote every graph; atomic-commit PD-4) | `_diagnose` raises a false `Conflict` | The caller still gets the false `Conflict` of atomic-commit PD-4 when the diagnosis cannot tell; when the diagnosis finds the commit applied, the session asks whether its activity is stored and publishes it if so (D-6 a). What is published is always what is recorded |
| A remove of a root another writer removed first | The request writes nothing, and the activity is not in the provenance graph | The call succeeds as before (atomic-commit PD-17e); no activity is recorded or published (D-5 a) |
| A `Served` with a statement about another subject, a type or a session-filled predicate | The `Served` constructor | `ValueError`; no request (D-5 b) |
| A `Served` given to a session that neither records nor has a hook | When the transaction opens | `ValueError` (D-6 h) |
| The activity IRI already exists | The id guard fails; diagnosis finds the IRI in the provenance graph | `Conflict` whose message names the activity IRI; nothing written |
| The same `Served` in a second transaction | A flag on the `Served` | `RuntimeError` before the request |
| `UnitOfWork.commit(batches=True)` with a command | Checked first | `ValueError`; nothing written |
| A command with a toolkit-filled slot set | `handle` checks the `TOOLKIT_FILLED` slots (eight from stage 2) | `InvalidBody` naming the slot; the handler does not run |
| No handler along the hierarchy | The MRO walk ends | `LookupError` naming the class |
| The handler raises | — | The exception reaches the caller; commits it already made stand and were published |
| An observer raises | `publish` catches | Logged with the observer's name; the others run; the commit stands |
| An observer sends the command it observes | The count passes `limit` | `MessageLimitExceeded` from `handle`; earlier commits stand |
| An observer commits on its session outside `handle`, in a loop | The nesting count passes `limit` | Logged as the observer's error (`MessageLimitExceeded`); the loop ends |
| `work.send` outside `handle` | `Work` has no queue | `RuntimeError`, logged as the observer's error |
| A queued command fails | `handle`'s loop catches | Logged; the queue goes on; `handle` returns the first command's result |
| The process stops between the commit and an observer | Not detected | The activity is stored; the observer never runs (DEC-11) |
| Restore of a dump with a provenance graph | `check_graphs` | Accepted and rewritten to the new tenant |
| A recorded IRI policy without `provenance_template` | The policy guard | Read as the default; the service starts |
| A consumer IRI policy whose `provenance_template` collides with another graph | `_require_distinct_graphs` | Refused at start, as for `meta` and `registry` |
| A stored class refers to a layer-3 activity class | `activity_direction` | `make generate` fails naming the slot |
| A stored record of a subclass whose class the schema no longer has | It still carries `rp:Transition` | Read as a `Transition` |
| An old `rp:TransitionRecord` graph | Not read by `transitions` | It stays a registered aggregate: `referrers` of its aggregate lists it and a remove no longer drops it (PD-1 item 4). The PR of stage 2 says so under `BREAKING CHANGE:`, with the `DELETE` that clears them |
| A handler commits a second time with its command | The `Served` flag | `RuntimeError`; the first commit stands |
| An observer writes the aggregate it observes | Not detected | The caller's unit of work is stale and conflicts on its next commit; the how-to says an observer should not write what it observes |
| A task an observer starts and does not await | Not detected | It runs with a finished `Work`; `send` raises `RuntimeError` there |
| A `Served` whose id is not a `urn:uuid:` | Checked when the transaction opens | `ValueError` |
| A root with no `rdf:type` | — | Its event has no `rp:entityClass` |

## Risks / Trade-offs

- **RISK-1 Many existing tests see a new graph or a longer request** (likely; medium). Tests that
  compare a whole dataset, count graphs or pin the request text fail in stage 2. Mitigation: task
  2.2 owns them; each is fixed by asserting the provenance content or by narrowing to aggregate
  graphs, never by `record_activities=False` (allowed only where a test is about the unrecorded
  path, with a comment).
- **RISK-2 The provenance graph grows without bound** (certain; low now). No pruning (DEC-10).
  PD-12 measures commits against 20 000 activities. Accepted; a purge comes with erasure (DEC-13).
- **RISK-3 The fake store copies the dataset on every update**, so unit and perf tests slow down
  as records accumulate (likely; low). Mitigation: watch `make test-perf`'s 2.0 s budget in 2.2; if
  it fails, report to the lead (do not raise the budget silently).
- **RISK-4 Other sessions change `services/session.py`** (likely; medium). Rebase on `develop`
  before every PR, keep both sides; a generated file takes `develop`'s version, then
  `make generate`.
- **RISK-5 A consumer on `develop` holds old transition records** (possible; low). Accepted by the
  developer (PD-1 item 4).
- **RISK-6 Personal data** (the principal) in records that are never deleted (certain; accepted,
  DEC-13).
- **RISK-8 `make generate` has not been run on PD-2's schema** (a class with no identifier as an
  owned inlined part, the moved slots, `PostReply is_a: PostComment`, `DeleteFile is_a: Remove`,
  an annotation in `slot_usage` reaching the induced slot of a subclass;
  possible; medium). Task 1.1 is first and finds out; a refusal by LinkML or the generator comes
  back to the lead before 1.3.
- **RISK-9 Breaking changes for consumers on `develop`** (certain; low): `TransitionRecord` leaves
  the public API, and every consumer test on the fake store now sees a provenance graph. The lead
  writes both under `BREAKING CHANGE:` in the commits and PR of stage 2.
- **RISK-7 The JSON-LD round trip may not hold for blank-node parts with `prov:activity` back
  links** (possible; medium). It is task 1.3, first in the EPIC after the model, so a failure
  changes PD-3 before anything depends on it; the fallback is to drop `prov:activity` from the
  parts' model and write it in the session only.

## Open Questions

None. The developer answered the round of 2026-11-14 (inputs/seed.md).
