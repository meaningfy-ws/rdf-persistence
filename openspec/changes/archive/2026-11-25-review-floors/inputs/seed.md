# Seeds: review-floors (secondary; never groomed)

The seven seed issues of meaningfy-ws/rdf-persistence, verbatim (body and comments), fetched
2026-11-22 with `gh issue view <n> --json ...`. The EPIC (`proposal.md`) supersedes them but does
not replace them.

---
## #252 Referrer guard: the remaining follow-ups of #227
state: OPEN | labels:  | author: costezki | created: 2026-11-21T14:29:40Z

### Body

The rest of #227, left out of #251, which did only the items that keep behaviour unchanged: the judged root named explicitly, `ReferrerRow` as a generated record, and the guard lifted out of `Transaction` into `persistence/services/referrers.py`.

## Changes behaviour

- `_types_of` returns `[""]` for an untyped root, so the same-commit check sees a referrer the store guard never would; return `[]`.
- The generic DELETE route opens a collaboration for every class; open it only for a refusing class (#227 comment, S1).
- Diagnosis of a refused cascade reads all rows of every referenced root; only the first needs rows, the rest an `ASK` (L1 S1).
- `Aggregates.remove(readable)` keyword-only like its siblings.

## Structure and docs

- `more_count` lives in `rp_api_entrypoints.yaml`, its twin `hidden_count` in `rp_collaboration_services.yaml`: give the pair one home.
- `collaboration-layers` import contract: add `referrer_naming` and `referenced_removals` (full review L3 W1).
- Small: `referrers & allowed` computed twice and `shown` a list in `ReferencedRemovals.in_use`; `named()` takes `list`; the `InUse` message's number; `_problem(schema: str)` to a model type.
- Docstrings: `in_use_problem` (the referrers come from the diagnosis read or the same-commit check, S2); `Aggregates.remove` should warn that an unfiltered `InUse` must not be shown to a caller by name (L1 S2); the `in-use` slug description in `rp_api_entrypoints.yaml` (S3).

## Tests

- `author_iri(n)` and the `Author`/`writtenBy` IRIs in `tests/toy.py`; the session test files' shared stub, opener and fixture in a `conftest.py`.
- A test of `KeyConflict` winning over `InUse` (PD-4); a test that the PD-5 type read is skipped when no link names a removed root.

The D-T-1 test item is done: #226 replaced it (#251).


### Comments

---
## #235 nested-collections follow-ups: the member-class race and the floor
state: OPEN | labels:  | author: costezki | created: 2026-11-21T09:51:45Z

### Body

Follow-ups of `nested-collections` (#198, PR #234), accepted on 2026-11-21 with follow-ups. Each item is recorded in `openspec/changes/archive/*-nested-collections/design.md`, Delivery decisions D-3 to D-5.

## The race (D-5): an absence guard
Across two transactions, T1 changes the member class of a collection S (it found no nesting collection holding S) while T2 makes a nesting collection P hold S, and T2 commits first. T1 has nothing to rely on, because version guards cannot state that a holder is absent, so both commit. Deep reads of P then raise `StoredDataInvalid` until a replace puts S's member class back. In the other order T2 relies on S's version and gets a `Conflict`. Closing it needs a guard that holds only if no nesting collection of S's class names S (a `FILTER NOT EXISTS` fragment in the commit's request, as the unique-key guards check absence).

## Under the floor, pinned by `xfail(strict=True)` tests in `tests/unit/collaboration/test_collaboration_nesting_adversarial.py`
- T-4: the same-transaction overlay ignores removes, so a cycle through a collection removed earlier in the same commit is refused (on the safe side).
- T-5: `delete_cascade` deletes a stored nested collection of another member class (written past the guard), where a deep read raises `StoredDataInvalid`.
- T-6: the "(k more)" of the cycle refusal counts the first way back the walk meets, not the shortest.

## Under the floor, from the review
- S-1: arguments threaded through three methods of the write guard's collection check.
- S-3: a static method that calls another by class name.
- C-1's check costs every replace of a collection one `graphs_with` query for its holders.

## Not tested
- A subclass of a collection class nested in its parent (the toy library has none).
- A sub-collection held by two nesting parents (allowed; the how-to says so).


### Comments

---
## #215 testkit-event-stream: test hardening from the stage 1 review
state: OPEN | labels:  | author: costezki | created: 2026-11-20T16:57:17Z

### Body

## Summary

These are test-hardening items from the stage 1 review of `testkit-event-stream` (PR #213). They
were recorded under the floor in its `design.md`, and none of them is a known defect of the
behaviour.

- W2: add tests for D-6 (an app that raises after the head returns the events so far and does not
  re-raise) and D-7 (a lifespan start-up longer than `timeout` does not raise), with
  `scenario-map.csv` rows.
- W5: add a subprocess check that `import rdf_persistence.testkit` does not load
  `rdf_persistence.testkit.streams` or `rdf_persistence.api.entrypoints.service` (PD-2), next to
  `test_testkit_root_does_not_import_the_heavy_libraries`.
- S1 (`test_events_route.py`, TC-37): commit a second visible sentinel and ask for `events=4`, so
  that "replay, then live, none twice" is told apart from a live-only delivery.
- S2 (TC-37b): resume from an id before the hidden replace, so that the replay itself holds a
  hidden activity.
- S3: in the default-route test, assert the sentinel's generation entity, not only the event type.
  In `test_open_event_stream.py`, check the event's data against the book, not against the
  event's own id.
- S4: document that a test holding several streams at once enters the lifespan itself, or set
  `rp_lifespan_started` before the start-up steps.
- S5: `pytest.raises(TimeoutError, match=re.escape(url))`.

`test-debt-paydown` also edits `test_events_route.py`, so its PLAN may take S1 to S3.


### Comments

---
## #214 testkit: a public way to wait until a stream follower is subscribed
state: OPEN | labels:  | author: costezki | created: 2026-11-20T16:57:15Z

### Body

## Summary

A consumer that tests "a commit reaches a reader" with `open_event_stream` (#204, PR #213) must
commit only after the stream is subscribed, since a follower hears only what follows. `EventHub`
offers no public way to tell that a follower is subscribed: it has only `subscribe` and `offer`.
The toolkit's own tests poll the private `hub._queues` (`listening`, `drained`; RISK-5 of
`testkit-event-stream`). The how-to `user-manual/test.adoc#event-stream` ("Hear a commit") tells
consumers to "wait until the stream is subscribed (your fixture, never a fixed sleep)", and a
consumer cannot write that fixture without private state or a sleep.

## Proposed capability

One of these:
- a public read on the hub, for example `EventHub.followers(tenant) -> int`;
- a testkit helper, for example `until_following(hub, tenant, n=1, timeout=...)`.

Then use it in the toolkit's `listening`/`drained` and in the how-to.

## Also owed on the same page (review W3 of PR #213)

The how-to does not state several outcomes that the docstring and `design.md` already record:
- the lifespan's start-up and shutdown are outside `timeout` (D-7);
- an app that raises after the head ends the read without re-raising (D-6);
- `RuntimeError` when there is no response;
- `ValueError` for a bad argument.

## Origin

Review finding W4 of `testkit-event-stream` stage 1 (PR #213), recorded under the floor in its
`design.md`.


### Comments

---
## #192 Follow-ups of domain-model-per-theme (review, under the floor)
state: OPEN | labels:  | author: costezki | created: 2026-11-19T14:21:44Z

### Body

Follow-ups from the review of `domain-model-per-theme` (#191), recorded under the floor in its `design.md` (§ Delivery decisions). None blocks 0.7.0; each is a Warning or Suggestion.

**Correctness, worth doing first**
- [ ] The E-2 check accepts any toolkit package, even one whose target does not have the module in its closure; the failure then shows only at import time. Check that the target with the named package generates the module (D-9).
- [ ] `is_stored_file` scans every class on every call (`schema_structure.py`), once per root class at a consumer's service start (`router.py`) and once per class at generation. Find the stored-file class once per view.

**Generator structure**
- [ ] The theme targets are recognised three ways (`METAMODEL_ROOT` file name, a module count in `render`, a root-set subset in `steps._stores_its_roots_here`). Declare it on `GenerationTarget` in `rp_generation.yaml`, and use the same property to skip writing the partial `shapes.ttl`, `context.jsonld` and frames the theme targets ship but nothing loads.
- [ ] `steps._toolkit_packages` and `_metamodel_root_names` re-read `pyproject.toml` (ignoring `--project`) and reload `rp.yaml` per target. Carry the targets on `Run`.
- [ ] `TOOLKIT_ROOTS` is patched in eleven modules by the tests (`ROOTS_USERS`); read it through one accessor or a `Run` field.
- [ ] `_generated_here` (generator) and `generated_schemas` (library) implement one predicate with two readers of `python_package`; keep one, and consider moving these generator-only helpers into `rdf_persistence_generation/`.
- [ ] `METAMODEL_ROOT` and `PYPROJECT` repeat existing constants; one home each, compare resolved paths.
- [ ] `enum_meanings`/`TENANT_STATE_IRIS` stay in `schema` for tests only, and the `vocabulary` docstring is stale; move the constant to the theme that owns `TenantState` or drop it.

**Tests**
- [ ] Asserts with `and` chains or no message (`test_no_old_module_paths.py`, `test_hard_check.py` with a `noqa: PT018`, `test_theme_domain_targets.py`, `test_theme_layout.py`); one duplicate test.
- [ ] One helper module for the theme map (now written in five places); test modules stop importing from test modules; read targets with `read_targets`, not raw TOML.
- [ ] Assert each `<theme>/domain/generated/` holds exactly its modules.
- [ ] The `v0.6.0` fixtures: compare Turtle by graph with a diff message, and decide whether they stay after 0.7.0.
- [ ] The hand-written `schema` import check repeats `themes-ordered`; keep only the behaviour tests.


### Comments

---
## #189 Follow-ups of target-kind-from-the-model: review floor and tutorial cold read
state: OPEN | labels:  | author: costezki | created: 2026-11-19T12:46:48Z

### Body

Follow-ups from `target-kind-from-the-model` (PR #188). They were left under the review floor or found by the cold read. Each is recorded in `openspec/changes/archive/2026-11-19-target-kind-from-the-model/design.md`, under Delivery decisions.

**Review findings left under the floor**
- [ ] **S2:** the theme failure ("is not in a theme: …", `rdf_persistence_generation/checks/boundary.py`) does not name the derived kind. The requirement "A target's kind is derived from its modules" says every failure names the target, the package and the derived kind. Either add the kind to the message or narrow the requirement.
- [ ] **S3:** `mixed_kind_problems` joins the technical modules with `,`, but PD-2 writes `m1, m2`. No test covers two technical modules.
- [ ] **S4:** `TargetKind(kind)` in `kind_folder_problems` is redundant now that `kind` is typed.
- [ ] **S1:** the spec scenario "a domain module in a technical target" says *toolkit target*, but its feature test runs a consumer target. Align the two.
- [ ] **S5:** `technical_models.feature`: one `Then` asserts three things (testing checklist rule 9).

**Tests**
- [ ] Six config-parsing tests keep packages with no layer (`test_freshness.py:343,365`, `test_generate_config.py:68,87,89`, `test_generation_inputs.py:82`). They never run the boundary step; move them for consistency (DEC-4).

**Docs: cold read of `tutorials/getting-started.adoc`**
- [ ] The page never mentions `domain/__init__.py` (it comes from this change). Python treats `domain/` as a namespace package without it, so it is optional, but the example ships one.
- [ ] The cold read's other 11 points were in the page before this change: terms used but never defined (`ServiceKit`, `UnitOfWork`, `generated_models`), no `cd library`, no sample output, and what the generator emits.


### Comments
#### costezki, 2026-11-19T22:23:59Z

Docs follow-up from a consumer (Mapping Workbench 2, planning its upgrade to v0.7.0, change `v2-01-toolkit-upgrade`, finding F-2): `user-manual/generate.adoc` says a technical module goes in its own target, and also that a request body your routes use stays in the domain target. It does not say which rule wins for an application's own route shapes (a consumer technical module such as `api.yaml` whose classes its services use), nor that their OpenAPI schemas then come from FastAPI rather than `openapi-components.json`. Proposed: one sentence and a short example in that page stating the rule for consumer route shapes.

#### costezki, 2026-11-20T09:08:54Z

**A further follow-up: a technical target re-emits the toolkit's TypeScript modules** (found by a consumer moving to v0.7.0, at `c671fefb`).

A consumer with two targets, a domain one and a technical one whose schema imports nothing but `linkml:types` and the toolkit's modules, gets the toolkit's TypeScript twice. The technical target's TypeScript folder holds, beside its own `api.ts` (33 lines), `rp_access.ts`, `rp_core.ts`, `rp_service.ts` and `rp_tenancy.ts` (617 lines), and its `index.ts` re-exports all of them. The domain target's folder emits the same modules, so the application has two sources for each toolkit type (`Action`, `GrantSet`, `TenantSummary`, …), and nothing in the technical module uses them.

**Expected:** a target emits the toolkit modules once, or a technical target references the toolkit's TypeScript instead of re-emitting it (for example, a key naming where the toolkit modules live, or emitting only the modules the target's own classes use). Both folders type-check today, so nothing is blocked; the cost is duplicate types that can drift if the two targets are ever generated from different toolkit versions.

**Acceptance:** Given two targets, a domain one and a technical one, When `rp-generate` runs, Then each toolkit TypeScript module is written once, and the technical target's `index.ts` exports only its own module's types (plus whatever its classes need).


---
## #125 aggregate-events: review findings under the floor
state: OPEN | labels:  | author: costezki | created: 2026-11-16T00:32:06Z

### Body

Follow-up of `aggregate-events` (archived, `openspec/changes/archive/2026-11-16-aggregate-events/design.md`, "End-of-epic review" and "Stage 1+2 review"): findings the reviews raised and the lead rejected under the floor (not Critical).

Triaged with the developer on 2026-11-16. Fixed by #129: the browser sample after a stream ends, tenant values in the logs, the traceback of a poison record, the import contract, the D-10 test, the docs (invalid envelope, Redis auth and TLS) and the checker's text fixes.

**Open: when a real load or a consumer needs them**
- A broker outage re-decodes the whole pending backlog every round, on every commit's wake; no backoff, no paging of `READ_PENDING`. (L4 W1)
- A resume (`Last-Event-ID`) loads up to 7 days of activities in one query; not paged. (L4 W5, L1 S1)
- No cap on open streams per principal or tenant; each re-reads access every second. (L4 W6)
- A broker outage also freezes browser streams (the hub is offered after the publish). (L4 S12)
- At shutdown the hub cannot end open streams (unverified). (L4 S13)
- Timing knobs (`access_ttl`, `keep_alive`, `resume_window`, `max_queue`, relay `interval`) are not exposed through `install_service`. (L3 S1, L4 S6)
- Tests: no test fails without `relay.wake()` on commit (L2 W-b); no redelivery by `claim_idle` within one run (L2 W-f); the Redis conformance `failing` hook closes the bus instead of stopping the broker (D-9, L2 W-d).

**Won't fix** (structure or style, no defect behind them): `receive` in `entrypoints` (L3 W1); plumbing IRIs built by `removesuffix` (L3 S2, L4 S1); the outbox queries in `Session` (L3 S3, L4 S4); tests reading private state, unasserted PUTs (L2 S-d); a plumbing-IRI test built like the code (L2 S-b); `tests/integration/adapters/` mapped to `events` only (L3 S5); FastAPI's 15 s ping beside the keep-alive (L4 S7); the small clean-ups (L4 S2, S3, S5, S8, S9, S10).


### Comments
#### costezki, 2026-11-16T00:55:15Z

From the stage 3 checker (not blocking): `entrypoints/sse.py:1` docstring and the comment at `entrypoints/router.py:415` still name the path `events` (it is `rp-events` since D-15); `tests/feature/test_events.py:3-5` docstring calls two different pairs of scenarios "the last two"; the `check-all` row of the durations table in `develop/index.adoc` shows 7287 tests from before the fix pass (the run on the stage 3 head passed 7355, 18 skipped, 13m00s).

#### costezki, 2026-11-16T16:28:15Z

Triaged with the developer on 2026-11-16. #129 fixes seven findings (browser sample, values in logs, poison traceback, import contract, D-10 test, docs, text fixes). The body now keeps open only what waits for real load or a consumer, and lists what will not be fixed.

