> Derives from: EPIC `message-bus` (proposal.md; design.md PD-1 to PD-23).
> Four stages, one PR each into `develop`. Type: Implementation.

Fixtures: the toy library (`tests/toy.py`: `TENANT`, `ADA`, `BOB`, `book_iri`, `dune`, `caller`,
`role`, `access`, `toy_mapper`; schema `tests/fixtures/library/`). Unit tests use the fake store
(`testkit/fakes.py`) through `tests/unit/services/conftest.py`'s session fixtures. "The provenance
graph" is `iris.provenance(TENANT)`; "the activities" are its subjects typed `prov:Activity`. RDF is
compared with `rdflib.compare.isomorphic` (develop/testing.adoc). The `generations` and
`invalidations` of a model are compared without order, by `(entity, entity_version)` (PD-4). Every
task is test-first. After a schema change: `make generate`, commit the generated files,
`make refresh-snapshot` and review its diff. After each task: `make test-changed` (after changing
`domain` or a port in `services`: `make test-fast`), `make check-quality`, `make clean-code`. Each
stage closes with a rebase on `develop`, `make check-all`, `make test-containers`,
`openspec validate message-bus --strict`, a PR into `develop` (`Refs: message-bus`), merged on
green CI.

## 1. The model and the PROV shape (stage 1)

- [x] 1.1 Schema (PD-2; RISK-8). `rp_provenance.yaml`: the four `Activity` slots, `Generation`,
  `Invalidation`, `Add`, `Replace`, `Remove`, the moved `used_resource` and `started_at_time`. The
  annotations `toolkit_filled` and `payload`: the `RpAnnotation` enum
  (`rdf_persistence/model/rp_core.yaml`) and `generation/checks/hard.py` `ALLOWED_ANNOTATIONS`.
  `services/vocabulary.py`: `TOOLKIT_FILLED`, `SESSION_FILLED`. `make generate`; add `rp_provenance` to the model
  sets (`entrypoints/kit.py`, `tests/toy.py` `MODULES`); export the new classes from
  `rdf_persistence/__init__.py` and `tests/unit/test_public_api.py`. `TransitionRecord` is
  untouched in this stage and still generates. Test first in
  `tests/unit/generation/test_metamodel_schema.py`. If LinkML or the generator refuses a construct,
  stop and report it to the lead.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `metamodel()` slots of `Activity` | the four new slots, optional; `generations` and `invalidations` owned and multivalued |
| TC-02 | `vocabulary.TOOLKIT_FILLED`; `SESSION_FILLED` | each exactly `started_at_time`, `ended_at_time`, `was_associated_with`, `generations`, `invalidations` |
| TC-02a | `Replace(id=…, was_associated_with=[ADA])` through the mapper and back | one `prov:wasAssociatedWith` IRI; the same model |
| TC-03 | `Generation(activity=…, at_time=…, entity=…)` without `entity_version`; the same with it and no `entity_class` | a validation error; valid |
| TC-04 | `TransitionRecord` after the slot move | same generated fields and stored triples as before (`test_mapper.py`'s round trip stays green unchanged) |

- [x] 1.2 The provenance graph in the IRI policy (PD-5). `rp_service.yaml` `IriPolicy.provenance_template`;
  `make generate`; `domain/iris.py` `Iris.provenance`, the fourth probe; `domain/tenant_move.py`
  `check_graphs`. Tests first beside the existing tests of `Iris`, `check_graphs`/`rewrite` and
  `guard_iri_policy` (find them with `ast-grep`; `tests/unit/domain/`, `tests/unit/services/`).

| ID | Input | Expected |
|---|---|---|
| TC-05 | `DEFAULT_IRIS.provenance(TENANT)` | `<TENANT>/provenance`; not an aggregate IRI, not a loaded graph, not an aggregate graph |
| TC-06 | a policy with `provenance_template` equal to `registry_template` | refused at construction, as two equal graph templates are today |
| TC-07 | a recorded policy JSON without `provenance_template`, default settings | the guard passes (no `IriPolicyChanged`) |
| TC-08 | `check_graphs` on quads in `<TENANT>/provenance` | accepted |
| TC-09 | `rewrite` of a provenance quad `<urn:uuid:a> rp:entity <old tenant>/books/1` to a new tenant | graph name and object carry the new tenant; the subject is unchanged |

- [x] 1.3 The shape and its round trip (PD-3, PD-4; RISK-7). After 1.1. `services/session.py`:
  `activity_triples(activity, types) -> list[Triple]` (the subject's types, the filled slots, the
  parts as blank nodes) from vocabulary constants (new constants in `services/vocabulary.py`), not
  called by the commit yet. `generation/extensions/jsonld_context.py` (`build_frame`, `render_frame`) and
  the step that calls them: frames for `Activity` and its descendants in a target's closure, tested
  in `tests/unit/generation/test_ext_jsonld_context.py`. Test first in
  `tests/unit/services/test_activity_shape.py`; the JSON-LD leg uses `testkit.round_trip` or its
  parts. If TC-12 or TC-13 cannot hold with the `prov:activity` back link, stop and report
  (RISK-7's fallback is the lead's to choose).

| ID | Input | Expected |
|---|---|---|
| TC-10 | a `Replace` with one generation and one invalidation; `activity_triples(model, [rp:Replace, prov:Activity])` | isomorphic to the Turtle of design.md PD-3 (parts as blank nodes) |
| TC-11 | the same model through `toy_mapper.to_graph` | isomorphic to TC-10's graph minus `(a, rdf:type, prov:Activity)` |
| TC-12 | the same model → `model_dump(mode="json")` → expanded with the generated context | isomorphic to TC-11's graph |
| TC-13 | TC-12's graph framed with the generated `Replace` frame and compacted | equals the model once the compact IRI of `entity_class` is expanded with the context (PD-24) |
| TC-14 | TC-10's graph read with `mapper.from_graph(Replace, …)` | equals the model (the ancestor type is ignored) |
| TC-15 | an `Add`, a `Remove`, and a bare `Activity` with two generations and one invalidation (for it `types` is `[prov:Activity]` and TC-11 removes nothing) | TC-10 to TC-14 hold for each (parametrized) |
| TC-16 | the generated frame files of the metamodel | one for `Activity`, `Add`, `Replace`, `Remove`; the root frames unchanged |
| TC-17 | a generation with no `entity_class` | no `rp:entityClass` triple; TC-11 to TC-14 hold |

## 2. The activity on every commit (stage 2)

- [ ] 2.1 `Served` and `Mapper.served` (PD-8). `services/provenance.py` (D-3 b): the `Served` dataclass;
  `services/mapper.py`: `served(command)`. Test first in `tests/unit/services/test_mapper.py`.
  Payload stripping is tested in 2.3 on `Transition`.

| ID | Input | Expected |
|---|---|---|
| TC-20 | `mapper.served(Replace(id="urn:uuid:1"))` | `types == [rp:Replace, prov:Activity]`; `triples` empty (the types are the session's to write); `activity.id == "urn:uuid:1"` |
| TC-21 | `mapper.served(Replace(id="urn:uuid:1", …))` with each `SESSION_FILLED` slot set (parametrized) | `triples` holds no statement of that slot |
| TC-21a | `mapper.served(Replace(id="https://example.org/x"))` | `ValueError` naming the id |

- [ ] 2.2 The commit records and publishes (PD-6 to PD-10; D-1). `services/session.py`:
  `Session(record_activities=True, on_commit=None)`, `open_session` likewise,
  `transaction(served=None)` and `served=` on `add_graph`, `replace_graph`, `remove`, the events
  collected per change, `_stored` returning the root's types, the activity operation, the id guard
  and its diagnosis, the hook. `services/tenancy.py`: `False` for the system database.
  `testkit/fakes.py`: `fake_session` passes both through. Fix the tests that now see the provenance
  graph (RISK-1); if more than 40 existing tests need a change, report the count and the three most
  common causes to the lead before changing them. Test first in `tests/unit/services/test_session_activity.py`. **Riskiest task:
  the adversarial tester runs after it.** Run `make test-perf` once and report it (RISK-3).

| ID | Input | Expected |
|---|---|---|
| TC-22 | `session.add_graph(b1, dune)` | one activity typed `rp:Add`, `prov:Activity`; principal ADA; start ≤ end; one generation: entity b1, class Book, version = the returned token; no invalidation |
| TC-23 | `replace_graph(b1, …, v1)` → v2 | one `rp:Replace`; generation version v2, invalidation version v1, both class Book |
| TC-24 | `remove(b1, v2)` | one `rp:Remove`; one invalidation, version v2, class Book |
| TC-25 | a transaction that adds b1 and b2 | one `rp:Add` with two generations |
| TC-26 | a transaction that adds b3 and removes b1 | one activity typed `prov:Activity` only |
| TC-27 | a replace at a stale version | `Conflict`; the provenance graph is unchanged (compare before and after) |
| TC-28 | an empty transaction; a transaction with only `_require_present` | no request, no activity |
| TC-29 | `transaction(served=mapper.served(Replace(id=X)))` that replaces b1 | the stored activity's IRI is X |
| TC-30 | a second commit served with a fresh `Served` of the same id X | `Conflict` whose message names X; b1 unchanged; one activity X |
| TC-31 | the same `Served` object given to a second transaction | `RuntimeError`; no request sent |
| TC-32 | `Session(record_activities=False)`: an add | no provenance graph |
| TC-33 | `Tenancy.create` | the system database has no provenance graph; the tenant database has one `rp:Add` for the root, associated with the creator |
| TC-34 | `on_commit` recording its arguments; a replace | called once after the commit with a `Replace` equal to the stored record read through the mapper, and the session |
| TC-35 | `on_commit` that raises | the commit returns normally; the error is logged; the record is stored |
| TC-36 | `on_commit` set; a refused commit | not called |
| TC-37 | a remove of a book with two comments (dependents) | one `rp:Remove` with one invalidation (the book); the comments are gone (PD-1 item 6) |
| TC-38 | the operations of a one-add commit with no `served` (the fake store's `sent`) | exactly one more than on `develop`, before the release; one update request |
| TC-39 | a replace of the tenant root | one `rp:Replace` whose entity is the tenant IRI |
| TC-40 | dump then restore of a tenant with three activities | the restored tenant's provenance graph holds the three, entity IRIs under the new tenant |
| TC-40a | an add of a root with no `rdf:type` | the generation has no `rp:entityClass`; `on_commit` gets a valid model |
| TC-40b | a replace that changes the root's class from Book to Shelf | invalidation class Book, generation class Shelf |
| TC-40d | an add of a `Template` through `kit.application_session` | one `rp:Add` in the application database's provenance graph (`iris.provenance(iris.application)`) |
| TC-40c | a stale replace served with a fresh id | `Conflict` naming the book, not the activity IRI (existing reasons first) |

- [ ] 2.3 `Transition` replaces `TransitionRecord`, kept on delete (PD-11; DEC-13).
  `rp_workflow.yaml` (the class, `expected_version`, the three `toolkit_filled` annotations,
  `to_state`/`expected_version`/`body_value` `payload: true` in `Transition`'s `slot_usage`);
  `make generate`; `services/transitions.py` (`_store`, `transitions`, no `dependents`);
  `Session.activities`; `entrypoints/kit.py` (dependents); `services/vocabulary.py`;
  `rdf_persistence/__init__.py` and `tests/unit/test_public_api.py`. Every test that names
  `TransitionRecord` or pins the deletion of records changes: `tests/unit/services/`
  `test_collaboration_workflow.py` (TC-90), `test_collaboration_workflow_adversarial.py` (re-add,
  remove paths, the racing remove), `test_mapper.py`, `test_schema_structure.py`,
  `tests/unit/generation/test_metamodel_schema.py`, `tests/unit/entrypoints/test_service_kit.py`,
  `tests/integration/store/test_collaboration.py`, `test_dependents_cost.py`; find the rest with
  `grep -rn TransitionRecord`. Test first in `tests/unit/services/test_collaboration_workflow.py`.

| ID | Input | Expected |
|---|---|---|
| TC-41 | ada moves b1 `draft` → `in_review` with comment "ready" | the provenance graph holds one `rp:Transition`: `prov:used` b1, from and to state IRIs, `rp:transitionComment` the comment, a generation and an invalidation of b1, a generation of the comment; no `body_value`, `to_state` or `expected_version` triple |
| TC-42 | TC-41 | the tenant has no graph under `rp-transitions` and no registry entry for a record |
| TC-43 | two moves, then `collaboration.transitions(b1)` | two `Transition`s, oldest first, each with states, principal and time, as the old records gave |
| TC-44 | TC-43, then remove b1 | the two activities are still in the provenance graph, with a third (`rp:Remove`); the comments are gone |
| TC-45 | TC-44, then `transitions(b1)` | `NotFound` (the aggregate is read first) |
| TC-46 | a session-holder adds b1 again after TC-44; `transitions(b1)` | the two old transitions (PD-11 consequence; the old test asserted none) |
| TC-47 | `collaboration.referrers(b1)` after a transition with a comment | as before: no record among the referrers |
| TC-48 | a transition refused (stale version; wrong role) | no activity |
| TC-49 | an activity typed `rp:Transition` and a subclass IRI the schema does not know, `prov:used` b1 | `transitions(b1)` returns it as a `Transition` |
| TC-49a | `Transitions._store` given a `Transition` with a forged `from_state_iri` | the stored record has the computed state, once |
| TC-49b | `vocabulary.TOOLKIT_FILLED` | also `from_state_iri`, `to_state_iri`, `transition_comment` (TC-02 updated); `SESSION_FILLED` unchanged and a subset |
| TC-49c | `mapper.served(Transition(id=…, used_resource=b1, to_state="in_review", expected_version=v1, body_value="x", from_state_iri=s1))` | `triples` hold `prov:used` and the from state, none of the three payload slots; `activity` has the three payload slots None |

- [ ] 2.4 Cost (PD-12). `tests/integration/store/test_activity_cost.py` (slow, container):
  measurement (b), the 20 000 activities preloaded with a few bulk `INSERT DATA` updates through
  the store, not through commits; re-run IT-06
  (`tests/integration/store/test_transaction.py::test_it06_a_commit_of_the_default_limit_of_new_books_is_one_update_within_30_s`). Record both in
  `docs/modules/ROOT/pages/develop/index.adoc` (durations table) and report the figures to the lead.

| ID | Input | Expected |
|---|---|---|
| TC-50 | 20 000 activities preloaded; 200 sequential replaces, recorded and unrecorded | prints both means; asserts only that every commit succeeded and that 200 activities were added |

- [ ] 2.5 Docs of stage 2. The deltas `specs/rp-workflow/spec.md` and
  `specs/rp-reverse-references/spec.md` of this change already say records are kept; align
  `howto/workflow.adoc` (the "history is deleted" paragraph), `questions.adoc` (the delete answer),
  `architecture/data-flows.adoc` (delete removes dependents; the transition flow),
  `architecture/index.adoc` (Collaboration row), `architecture/generation.adoc` (where it names
  `TransitionRecord`), `develop/index.adoc` (the `test_dependents_cost.py` row). `make check-docs`.

## 3. The bus, the checks, the toy (stage 3)

- [ ] 3.1 `MessageBus`, `Work`, `command`, `MessageLimitExceeded` (PD-13). `services/messagebus.py`,
  `domain/exceptions.py`, exports. Test first in `tests/unit/services/test_messagebus.py`, with
  test-local Python subclasses of the generated `Replace` and fake handlers: this task tests
  dispatch only and stores nothing.

| ID | Input | Expected |
|---|---|---|
| TC-60 | a handler for `Replace`; `handle(command(Replace), c)` | the handler is called once with the command and a `Work` whose `collaboration` is `c`; `handle` returns its result |
| TC-61 | handlers for `Activity` and `Replace`; a subclass of `Replace` | the `Replace` handler (nearest) |
| TC-62 | no handler along the hierarchy | `LookupError` naming the class |
| TC-63 | a command with one toolkit-filled slot set: the five of TC-02 on a `Replace`, the three of TC-49b on a `Transition` (parametrized) | `InvalidBody` naming the slot; the handler is not called |
| TC-63a | a command with `generations=[]` | handled (an empty list is not set) |
| TC-64 | the handler raises `Conflict` | `handle` raises it |
| TC-65 | observers on `Activity` (o1) and `Replace` (o2, o3); `publish(Replace…)` | called in the order o2, o3, o1, once each |
| TC-66 | o2 raises | logged with o2's name; o3 and o1 still run; `publish` returns |
| TC-67 | a handler for `Replace` that calls `publish` (as a commit would) and an observer that sends a `Remove` command | the `Remove` handler runs after the `Replace` handler returned |
| TC-68 | as TC-67 but the observer sends the command it observes; `limit=5` | `handle` raises `MessageLimitExceeded` naming 5; the handler ran 5 times |
| TC-69 | `work.send` from a `publish` outside `handle` | logged `RuntimeError`; nothing handled |
| TC-70 | a queued command whose handler raises | logged; later queued commands run; `handle` returns the first result |
| TC-71 | a key that is not an `Activity` subclass; `limit=0` | `ValueError` at construction |
| TC-72 | outside `handle`: an observer that calls `publish` again on every activity; `limit=5` | `publish` raises `MessageLimitExceeded` at depth 6; the observer ran 5 times |
| TC-72a | an observer inside `handle` that calls `bus.handle` with the observed command; `limit=5` | the outer `handle` raises `MessageLimitExceeded` (the nested call joins the count) |
| TC-72b | two `handle` calls in two asyncio tasks | each has its own count and its own `Work` |
| TC-72c | `command(Replace)` twice | two ids, both `urn:uuid:` |

- [ ] 3.2 The generator checks and the toy (PD-20, PD-21, PD-23). `generation/checks/boundary.py`,
  `hard.py`, `generation/model/rp_generation.yaml` (the rule values); `make generate`;
  `tests/fixtures/library/books_activities.yaml`, `library.yaml`; `tests/toy.py`. Tests first in
  `tests/unit/generation/test_boundary_check.py` and `test_hard_check.py` (planted-fault rows).

| ID | Input | Expected |
|---|---|---|
| TC-100 | the toy with `books_activities.yaml` | `make generate` passes: no ownership problem for `ApproveBook` or `ShelveBooks`; a frame for each in the toy's generated folder, and for the toolkit's activity classes |
| TC-101 | planted: `Book` gains a slot ranging over `ShelveBooks` | `[activity_direction]` naming the slot |
| TC-102 | planted: `Book` gains a slot ranging over `Activity`; a planted aggregate root that `is_a: Activity` referred to by `Book` | no problem |
| TC-103 | planted: `ShelveBooks` gives `slot_usage` for `started_at_time` | `[toolkit_filled]` naming the class and the slot |
| TC-103a | planted: `ShelveBooks`'s `slot_usage` makes `shelf_note` `payload: true` and required | `[toolkit_filled]` naming the slot |

- [ ] 3.3 Wiring: `bootstrap`, the `Transition` handler, `UnitOfWork(served=)`, the kit (PD-14 to
  PD-17). `services/messagebus.py`, `services/mapper.py`, `services/collaboration.py` (`session`,
  `mapper`, `command=`), `services/transitions.py`, `services/tenancy.py`, `entrypoints/kit.py`,
  `entrypoints/service.py`. Tests first in `tests/unit/services/test_messagebus_wiring.py` and
  `tests/unit/entrypoints/test_service_kit.py`.

| ID | Input | Expected |
|---|---|---|
| TC-73 | `bootstrap(mapper=toy_mapper)`; `handle(command(Transition, used_resource=b1, to_state="in_review", expected_version=v1), c)` | b1 is in review; returns the new version; one `rp:Transition` activity with IRI = the command's id |
| TC-104 | the same with `ApproveBook`, no handler for it | the toolkit handler runs; the stored activity is typed with the toy's `ApproveBook` IRI, `rp:Transition` and `prov:Activity` (the spec's "extension without its own handler") |
| TC-75 | TC-104 with observers on `Transition` and `Activity` | each gets one `ApproveBook` with `to_state`, `expected_version` None and states, times, principal, events set (design.md, worked example) |
| TC-105 | TC-104's stored activity through TC-12 to TC-14 with the toy context and frame | the round trip holds for a consumer subclass (PD-4) |
| TC-76 | `bootstrap(commands={ShelveBooks: h}, notifier=fake)` where `h(command, work, notifier)` | `h` receives `fake` |
| TC-77 | `bootstrap(notifier=fake)` with no handler or observer naming it | `ValueError` naming `notifier` |
| TC-78 | `bootstrap(commands={Transition: mine})` | `mine` replaces the toolkit handler |
| TC-106 | a `ShelveBooks` handler that replaces two books through `work.unit_of_work()` and commits | one `ShelveBooks` activity, `shelf_note` stored, two generations and two invalidations; observers called once |
| TC-79 | TC-106's handler commits a second time through `work.unit_of_work()` | `RuntimeError`; the first commit stands |
| TC-79a | an observer of `ShelveBooks` that adds a book through `work.unit_of_work()` | a second activity typed `rp:Add`; no conflict |
| TC-80 | `UnitOfWork(served=…).commit(batches=True)` | `ValueError`; nothing written |
| TC-80a | `work.unit_of_work()` on a bus built without a mapper | `RuntimeError` |
| TC-81 | a kit whose `bus` is set; a generic HTTP replace of a book | the bus's `Activity` observer gets one `Replace` associated with the caller (the spec's "a generic replace") |
| TC-82 | a kit with no bus | commits record activities; nothing is published |
| TC-83 | `collaboration.transition(…)` called directly, the kit has a bus | the `Transition` observers run (DEC-6) |

## 4. The comment and file commands, the testkit, the docs (stage 4)

- [ ] 4.1 `PostComment`, `PostReply`, `DeleteFile` (PD-18, PD-19, PD-15). `rp_discussion.yaml`,
  `rp_files.yaml`; `make generate`; add `rp_files` to the model sets if missing;
  `services/discussion.py`, `services/collaboration.py`, `services/file_removal.py` and its caller
  in `entrypoints/kit.py` (the mapper), `services/messagebus.py` (the two handlers); exports. Tests
  first beside the existing tests of comments and of `remove_with_files`, and in
  `test_messagebus_wiring.py`.

| ID | Input | Expected |
|---|---|---|
| TC-90 | `collaboration.comment(b1, "hi")` | one `rp:PostComment` (also typed `prov:Activity`): `prov:used` b1, one generation (the comment); no body text in the provenance graph |
| TC-91 | a reply to that comment | one `rp:PostReply`, also typed `rp:PostComment`; `rp:repliesTo` the comment |
| TC-92 | `handle(command(PostComment, used_resource=b1, body_value="hi"), c)` | the comment is stored; returns its IRI; the activity's IRI is the command's id |
| TC-93 | an observer on `PostComment`; a reply is posted | the observer gets the `PostReply` |
| TC-94 | `remove_with_files` of a stored file | one `rp:DeleteFile` (also `rp:Remove`, `prov:Activity`) with one invalidation |
| TC-95 | `handle(command(DeleteFile, used_resource=f1), c)` with `bootstrap()` | `LookupError` (no handler, PD-1 item 2) |

- [ ] 4.2 Testkit and feature scenarios. `testkit/`: `RecordingObserver` (PD-22), exported and
  covered in `tests/unit/testkit/`. `tests/feature/`: `messages.feature` with the seven scenarios of
  `specs/rp-messages/spec.md` on the toy classes, and its step module beside the existing ones.

- [ ] 4.3 Docs. `architecture/index.adoc` (the building block; no consumer terms),
  `architecture/data-flows.adoc` (a commit with its activity; publish), a new
  `howto/event-driven.adoc` (bootstrap, a command, an observer, modelling use-case activities per
  P-0001, the limits: one command one commit, at most once, `send` outside `handle`, an observer
  should not write what it observes, the false conflict), linked from `howto/adopt.adoc` and the
  nav; `questions.adoc` (the questions the page answers); `openspec/changes/README.md` row.
  `make check-docs`. A cold reader subagent checks the how-to.

## Roadmap

- [x] 1.1 · [ ] 1.2 · [ ] 1.3 · PR 1 · [ ] 2.1 · [ ] 2.2 · (adversarial tester) · [ ] 2.3 ·
  [ ] 2.4 · [ ] 2.5 · PR 2 · [ ] 3.1 · [ ] 3.2 · [ ] 3.3 · PR 3 · [ ] 4.1 · [ ] 4.2 · [ ] 4.3 · PR 4

1.1 then 1.3; 1.2 touches other files than 1.1 except the generated ones, so it runs after 1.1 too.
3.1 and 3.2 touch disjoint files and may run in parallel; so may 4.2 and 4.3 after 4.1. Everything
else is sequential. The lead writes the `BREAKING CHANGE:` lines of stage 2 (RISK-9).

## Verification

Per stage: the TC tables above as tests, `make check-all`, `make test-containers`,
`openspec validate message-bus --strict`, CI green. For the whole change: every scenario of
`specs/rp-messages/spec.md` and of the two modified specs has a test (4.2 and TC-41 to TC-49); the
clarity gate ≥ 9/10 on this PLAN; the acceptance demo offered to the developer after PR 4.
