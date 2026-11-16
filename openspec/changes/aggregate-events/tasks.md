> Derives from: EPIC `aggregate-events` (proposal.md DEC-1 to DEC-10; design.md PD-1 to PD-16).
> Three stages, one PR each into `develop`. Type: Implementation.

Fixtures: the toy library (`tests/toy.py`: `TENANT`, `ADA`, `BOB`, `book_iri`, `dune`, `caller`,
`role`, `access`, `toy_mapper`; schema `tests/fixtures/library/`). Unit tests use the fake store
(`testkit/fakes.py`) through `tests/unit/services/conftest.py`'s session fixtures. "The provenance
graph" is `iris.provenance(TENANT)`; "pending" means an `rp:pendingSince` triple there (PD-1);
"relayed" an `rp:relayedAt` triple. RDF is compared with `rdflib.compare.isomorphic`. Every task is
test-first. After a schema change: `make generate`, commit the generated files,
`make refresh-snapshot` and review its diff. Task gate: `make test-changed check-quality`
(`make test-fast check-quality` after changing `domain` or a port in `services`). No test sleeps:
`testkit.wait_until`, or `Relay.run_once()`. Each stage closes with a rebase on `develop`,
`make check-all`, `make test-containers`, `openspec validate aggregate-events --strict`, a PR into
`develop` (`Refs: aggregate-events`), merged on green CI. TC ids are not contiguous (TC-29, TC-30
unused; letters mark cases added by the PLAN's attack).

## 1. The outbox and the relay (stage 1)

- [x] 1.1 Spike (PD-4; RISK-1). No product code. In `temp/spike_faststream/` run, with
  `uv run --isolated --with 'faststream[redis]==0.7.8'` against `docker run redis:8`, a script
  that proves the four points of PD-4 with a generated model (`Replace` from
  `rdf_persistence.domain.generated`). Write
  `openspec/changes/aggregate-events/evidence/spike-faststream.md`: each point, held or not, with the
  API used (exact FastStream calls), and the trim and redelivery mechanisms chosen (RISK-1's
  fallbacks when needed). A point that fails with no fallback: stop and report to the lead.

| ID | Input | Expected |
|---|---|---|
| TS-1 | publish `Replace` JSON with four string headers; subscribe | body validates into `Replace`; headers equal |
| TS-2 | consumer raises before ack; restart the consumer in the same group | the message is delivered again |
| TS-3 | a message older than the trim age (age set to 1 s for the spike) | gone after the trim |
| TS-4 | the AsyncAPI generator over the app | a document naming the stream and the payload schema |

- [x] 1.2 The marks (PD-1, PD-2, PD-14). `services/vocabulary.py` `PENDING_SINCE`, `RELAYED_AT`,
  `PUBLICATION_FAILED`; `services/session.py` `_record` adds the pending mark with the store's
  `NOW()`; `services/tenant_dump.py` `restore` drops the three predicates before the import. Tests
  first in `tests/unit/services/test_pending_mark.py` (new) and beside the restore tests.

| ID | Input | Expected |
|---|---|---|
| TC-01 | add, replace, remove of `dune` (three commits) | three activities, each pending once; `pendingSince` non-decreasing in commit order |
| TC-02 | `open_session(record_activities=False, on_commit=hook)`; add | no activity, no mark; the hook gets the activity |
| TC-03 | a stale replace; an invalid body; a key conflict | no new activity, no new mark |
| TC-03a | an overtaken commit (the false `Conflict` of atomic-commit PD-4, reproduced as its tests do) | the activity and its mark are stored |
| TC-04 | a commit on the application database | its activity is pending in the application provenance graph |
| TC-05 | dump a tenant holding one pending and one relayed activity; restore it | the restored provenance graph holds both activities, no mark, no `relayedAt` |

- [x] 1.3 The port, the envelope, the fake (PD-6, PD-7). `rp_service.yaml`: class `EventEnvelope` (D-4) and
  the optional `ServiceSettings.public_url`; `make generate`. `services/events.py`: `EventBus`,
  `Receive`, `context_link(settings) -> str`. `testkit/fakes.py`: `InMemoryEventBus`,
  `InMemoryBroker`. `testkit/event_bus_conformance.py`: TC-07 to TC-09 as a reusable suite taking a
  factory of two buses on one broker (like `store_conformance.py`), run here against the fake in
  `tests/unit/testkit/test_in_memory_event_bus.py`. Export the new public names from
  `rdf_persistence/__init__.py`, `rdf_persistence/testkit/__init__.py` and
  `tests/unit/test_public_api.py`.

| ID | Input | Expected |
|---|---|---|
| TC-06 | `context_link` with `public_url="https://lib.example"`; with none | `https://lib.example/context.jsonld`; `/context.jsonld` |
| TC-07 | two buses on one broker, both started; A publishes `(envelope, Replace)` | B's receiver gets an equal envelope and a body that validates into an equal `Replace`; A's receiver gets it too |
| TC-08 | B's receiver raises; B is closed and started again | B receives the same message again; A's does not |
| TC-09 | the bus told to fail the next publish (fake: a flag; Redis: the broker stopped) | `publish` raises; the next succeeds |

- [x] 1.4 Decoding (PD-16). `services/provenance.py` `activity_class_of`, `activity_class_named`,
  `decode_activity`; `services/session.py` the template `READ_PENDING` and
  `Session.pending_activities() -> list[tuple[str, Graph]]` (ordered per PD-5's first key), plus
  `Session.mark_relayed(iri)` and `Session.mark_failed(iri)` (one update each, the store's `NOW()`).
  Tests first in `tests/unit/services/test_decode_activity.py` and
  `tests/unit/services/test_pending_mark.py`.

| ID | Input | Expected |
|---|---|---|
| TC-41 | a stored `Replace`; a stored `Transition`; a stored consumer subclass of `Transition` with its own slot (the toy's, as in message-bus TC-105) | each decodes into its own class, the subclass with its slot |
| TC-42 | types `{prov:Activity, rp:Remove}`; an IRI of another namespace; `{prov:Activity}` only | `Remove`; `LookupError`; `Activity` |
| TC-43 | `pending_activities` after three commits, one relayed | two, in `pendingSince` order, without the plumbing predicates |
| TC-44 | `mark_relayed(a)` twice; `mark_failed(b)` | `a` relayed once, not pending; `b` failed, not pending |

- [x] 1.5 The relay (PD-3, PD-5). `services/relay.py` `Relay(tenancy, view, models, mapper,
  bus: EventBus | None, hub: Offer | None, *, deployment, context, interval=5.0)`, `wake()`, `run_once()`,
  `run()`. Tests first in `tests/unit/services/test_relay.py`. The lead runs the adversarial tester
  after this task.

| ID | Input | Expected |
|---|---|---|
| TC-10 | three commits in T; `run_once()` | the fake broker holds three messages in commit order, each envelope correct (tenant T, origin = deployment, class IRI, context); none pending; three relayed |
| TC-11 | two pending replaces of one book with equal `pendingSince` (written by hand in the fake store) | published in version order |
| TC-11a | a remove then an add of one IRI, the add's client clock earlier (fixed clocks) | published remove first (store order) |
| TC-12 | a commit; a new `Relay` on the same store (a restart); `run_once()` | the activity is published |
| TC-13 | `mark_relayed` fails after the publish (store fault injected); `run_once()` twice | published twice with the same id |
| TC-14 | bus fails on the 2nd of three activities of T; T2 has one | T: 1 published, 2 and 3 pending; T2's published; next round publishes 2 then 3 |
| TC-15 | a tenant in `DELETING`; a tenant in `behind`; a tenant whose database is gone | not visited / not visited / skipped; others published |
| TC-15a | a pending activity of a class the schema lacks, before a valid one | the first marked failed (ERROR logged), the second published in the same round |
| TC-16 | the store raises for T only; then an unexpected error in a whole round | T2 published in the same round; the loop survives the error and publishes after `wake()` |
| TC-17 | an activity recorded with no mark (before this EPIC) | never published |
| TC-18 | bus `None`; one pending activity; a recording `Offer` | relayed; offered once |
| TC-18a | `wake()` three times during a round | exactly one more round |

- [x] 1.6 Wiring (PD-15). `entrypoints/kit.py`: `kit.hub`, `kit.relay`; `_publish` calls
  `relay.wake()` after the in-process bus. `entrypoints/service.py`: `install_service(event_bus=
  None)`, the deployment check, the lifespan starts the bus's consumer with `kit.receive` (a stub
  that logs at DEBUG and returns; 2.2 fills it), then the relay task, and stops both. Tests first
  beside the existing lifespan tests (`tests/unit/entrypoints/`).

| ID | Input | Expected |
|---|---|---|
| TC-19 | app with the fake bus; a `POST` of a book | within `wait_until`, the broker holds its `Add` |
| TC-20 | app lifespan exits | the relay task is done; `close()` was called on the bus |
| TC-21 | app with no event bus; a `POST` | the activity is relayed (the relay runs) |
| TC-21a | `install_service(event_bus=…)` with settings whose `deployment` is empty | `ValueError` |

- [x] 1.7 Feature (spec rp-events, first two requirements). `tests/feature/events.feature` and
  `tests/feature/test_events.py`: "a stale write records nothing", "a restore publishes nothing
  again", "a crash between commit and publish", "events of one aggregate arrive in order", on the
  fake store and bus.

## 2. The broker (stage 2)

- [x] 2.1 The Redis adapter (PD-8; Q7). `pyproject.toml` extra `events`; `uv lock`.
  `rdf_persistence/testkit/containers/compose.yaml` service `redis` (`redis:8`, its port);
  `containers/fixtures.py` fixture `redis` and its marker, as the other container fixtures.
  `adapters/redis_events.py` `RedisEventBus`, built on the spike's calls. The conformance suite of
  1.3 against it in `tests/integration/adapters/test_redis_events.py` (marker `integration`).
  `.importlinter`: only `rdf_persistence.adapters.redis_events` imports `faststream` or `redis`.

| ID | Input | Expected |
|---|---|---|
| TC-22 | the conformance suite, Redis | TC-07 to TC-09 pass |
| TC-23 | `retention=timedelta(seconds=1)`; publish; wait past it (`wait_until`); publish again | the first entry is gone |
| TC-31 | a subprocess `python -c "import rdf_persistence, rdf_persistence.testkit, sys; assert 'faststream' not in sys.modules and 'redis' not in sys.modules"` | exits 0 |

- [x] 2.2 Incoming messages (PD-10). `entrypoints/kit.py` `receive(envelope, body)`. Tests first in
  `tests/unit/entrypoints/test_receive.py` with two kits sharing one `InMemoryBroker` and one fake
  store, deployments `lib` and `cat`, and a `RecordingObserver` on each. The feature scenario
  "another deployment's commit" in `tests/feature/incoming_events.feature` (its own file, so 1.7
  and 2.2 could run in parallel).

| ID | Input | Expected |
|---|---|---|
| TC-24 | `lib` commits a replace; both relay | `cat`'s observer gets it once, with a session on T whose principal is the toolkit's; `lib`'s observer got it once (in process), not again |
| TC-25 | a message of an unknown class; one whose body does not validate | WARNING logged; no observer; acked (not redelivered) |
| TC-26 | a message for a tenant `cat` lacks | WARNING; acked |
| TC-27 | `cat`'s store raises `StoreUnavailable` on the probe | not acked: redelivered when `cat`'s bus starts again |
| TC-27a | the tenant is in `cat`'s `behind` | not acked |
| TC-28 | an application-database activity | `cat`'s observer gets it with an application session |

## 3. Server-sent events (stage 3)

- [x] 3.1 The hub and the route (PD-9, PD-11, PD-12). `services/event_hub.py` `Offer`, `EventHub`;
  `services/` `visible_part`; `Session.relayed_since(iri, window, now)` with its template beside
  `READ_ACTIVITIES`; `entrypoints/router.py` the route on `fastapi.sse.EventSourceResponse`. Tests
  first in `tests/unit/services/test_event_hub.py`, `tests/unit/services/test_visible_part.py` and
  `tests/unit/entrypoints/test_events_route.py` (the app with the fake bus and `EventHub(max_queue=
  2)` where TC-36 needs it; the stream read with `httpx` until N events; a fixed clock).

| ID | Input | Expected |
|---|---|---|
| TC-32 | Bob follows T; Ada replaces `dune` | Bob gets `id: <activity>`, `event: Replace`, data validating into `Replace`; a `Link` header with `CONTEXT_REL` |
| TC-33 | Carol has a Prohibition of `read` on `dune`; `dune` and another book replaced | Carol gets the other book's event only |
| TC-34 | an activity with two generations, one hidden | sent with one generation |
| TC-35 | Carol's tenant grant removed mid-stream, then a commit; the same with no commit (keep-alive 0.1 s) | the stream ends in both |
| TC-36 | `max_queue=2`, three offers to a stream not read | that stream ends; another subscriber got all three |
| TC-37 | Bob reconnects with `Last-Event-ID` a1 after a2, a3 relayed | a2, a3, then a live a4; none twice |
| TC-37a | a1 relayed, then a0 (applied earlier, relayed later); resume from a1 | a0 is sent |
| TC-37b | resume from a1 when a2 is about a book Carol may not read; Carol resumes | Carol does not get a2 |
| TC-38 | `Last-Event-ID` unknown; one relayed 8 days ago; one never relayed | one `reset` event each, then live |
| TC-39 | a caller without `read` on T | `403` problem response, no stream |
| TC-40 | a follower of T2 when T commits; a commit on the application database | gets nothing |

- [x] 3.2 Feature: "a hidden aggregate" and "resuming a stream" in `tests/feature/events.feature`.
- [x] 3.3 Docs. `howto/event-driven.adoc`: the relay, the `events` extra,
  `install_service(event_bus=RedisEventBus(...))`, `deployment` (required, unique per broker) and
  `public_url`, incoming messages, idempotency by id, the two guarantees (RISK-9), loops (RISK-8),
  the SSE route and `Last-Event-ID`, a reader needs tenant `read` (RISK-5), single instance
  (RISK-4), what a message reveals (RISK-6). `architecture/index.adoc`: "Outbox, event bus and
  relay" and "server-sent events" built. `questions.adoc`: the question the section answers. The
  durations table in `develop/index.adoc` from the stage's ordinary runs. `make check-docs`.
- [ ] 3.4 Reconcile `proposal.md` with what was built (P-0004): an "As built" table, What Changes,
  Capabilities, Impact; the spec delta true of the code.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5 (then the adversarial tester) · [x] 1.6 ·
  [x] 1.7 · [x] 2.1 · [x] 2.2 — PR #124 (stages 1 and 2 as one PR, D-3)
- [ ] 3.1 · [ ] 3.2 · [ ] 3.3 · [ ] 3.4 — PR 3 (the last merge)

1.1, 1.2 and 1.3 touch disjoint files and may run in parallel; 1.4 after 1.2 (both in
`session.py`); 2.1 and 3.1 depend only on stage 1.

## Verification

Each task's TCs test-first and its task gate; per stage `make check-all`, `make test-containers`
(the Redis conformance from stage 2) and `openspec validate aggregate-events --strict`; the
PLAN scored by the clarity gate at ≥ 9/10 (`evidence/clarity-gate.md`).
