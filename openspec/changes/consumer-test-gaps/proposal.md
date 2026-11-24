<!-- Parents: issues #319, #320, #323 (MWB2 v2-03) and #332 (found in the review of #330,
     consumer-gap-fixes); openspec/specs/rp-testkit, rp-service-api, rp-uml-import.
     Seeds: inputs/seed.md. Q&A: inputs/qa.md (2026-11-24). P-0020: a bug fix gets a change.
     Serves (D-12): MWB2 v2-03, which arms faults with times=2 (#319), shows referrers without a
     label (#320) and wraps store.update for its concurrent-write scenario (#323); each workaround
     is removed once this ships. -->

# EPIC: Consumer test gaps: aimed faults, held commits, followable referrers, narrowed cardinality

## Appetite

**SMALL**: four gaps, each in one place, and existing structure reused. The work runs in three
stages by concern, one PR each: the testkit (#319, #323), the API (#320) and the generator (#332).

## Why

- **#319.** `FakeStore.on` arms a fault by call index across every caller. The kit's relay also
  calls `update`, to mark an activity relayed. A request that yields before its write can
  therefore lose the fault to the relay, and "the store fails the next write" answers 201 instead
  of 503. `Relay.paused()` already keeps the relay still, but no consumer-facing page says so.
- **#323.** A consumer cannot hold a commit until a second writer has read. To prove "two
  concurrent writes, one gets `Conflict`" it must monkeypatch `FakeStore.update` and match our
  SPARQL text.
- **#320.** A `409 in-use` answer names each referrer by IRI, class and slot. A client cannot
  form the generic `GET {tenant_segment}/{t}/{rp_path}/{id}` of a referrer from that, because no
  answer maps a referrer to its `rp_path` or its id, and the IRI policy promises no layout.
- **#332.** The converter writes a differing `required`/`multivalued` explicitly (#330, D-5), but
  a differing `minimum_cardinality` or `maximum_cardinality` still goes through `_shape_kwargs`,
  which skips `None`. A subclass that redraws an inherited `2..*` role as `1` therefore inherits
  `minimum_cardinality: 2`.

## Solution outline

- **The relay stays out of a fault test.** The testkit page shows `async with kit.relay.paused():`
  around the request. A feature test proves that inside the block the armed fault is the request's.
- **`FakeStore.hold(operation, until=n)`.** It is an async context manager. Inside it, the first
  `n` calls of `operation` wait until `n` of them are waiting, then all go on in arrival order. A
  hold that never fills releases its waiters after a timeout and fails on exit, so a test fails
  instead of hanging.
- **A referrer says where to read it.** `Referrer` gains two optional slots, `referrer_rp_path`
  and `referrer_id`, filled when the referrer's class is served and its IRI matches the policy's
  aggregate pattern. Both are set, or neither is. The 409 `in-use` answer and the referrers
  listing carry them alike.
- **A differing cardinality is written as the class's own bound.** For a cardinality on which the
  usages differ, each usage writes the bound of its own multiplicity: the lower bound for the
  minimum (0 and 1 included), and the upper bound for the maximum when it is finite (1 included).
  An unbounded upper bound under an `is_a` ancestor's finite one cannot be said in LinkML, so it
  is a converter problem.

## Key decisions

- **DEC-1:** #319 is answered by documentation and a feature test, with no new API: the fault
  test runs inside `kit.relay.paused()`. Rejected: `on(..., match=predicate)`, because the
  predicate reads our SPARQL text, the coupling #323 complains about (owner, round 1).
- **DEC-2:** #323 adds `FakeStore.hold(operation, until, timeout=5.0)`, an async context manager
  on the fake only. Rejected: a `before_update` hook (each consumer would build the barrier) and
  a barrier in `Session` (a test seam in production code) (owner, round 1).
- **DEC-3:** #320 adds optional `referrer_rp_path` and `referrer_id` to the shared `Referrer`,
  set together or not at all. Rejected: a read-by-IRI route (a new route and gate, beyond SMALL)
  and a class→`rp_path` map in the TypeScript (the client would still cut the id out of the IRI)
  (owner, round 1).
- **DEC-4:** #332: `usage_of` writes each differing cardinality as the usage's own bound, and a
  usage whose upper bound is unbounded under a finite one of an `is_a` ancestor is a converter
  problem (owner, round 1). Rejected: staying silent (a wrong model), and refusing every widening
  (it rejects the issue's own reproduction).
- **DEC-5:** the new #332 problem is an error, as every converter problem is (owner, round 2: the
  "make it a warning" option was left unticked).
- **DEC-6:** three stages and three PRs into `develop`, in the order testkit, API, generator. The
  stages share no code, so the order only fixes review order. This EPIC lands with stage 1's PR.
  A release follows the last merge, so the consumer can drop its workarounds.

## Rabbit-holes

- #323: the relay's own `update` counts towards `until` unless the relay is paused (RISK-3). The
  docstring and the testkit page say so. `hold` does not filter by payload (No-gos).
- #323: a held call records nothing in `sent` until it is released, so `sent` and `on` see calls
  in release order. Check that `on(after=…)` still counts the same way.
- #320: a root of several classes gives one referrer row per class. Only a row whose class is
  served gets the pair. Do not invent a "primary class".
- #320: the referrers listing and the 409 handler are built in different layers. One helper names
  the pair for both, so they cannot drift.
- #332: `minimum_cardinality: 0` is new in generated output. Check that the Pydantic, SHACL and
  JSON-Schema targets accept it and add no constraint. `SchemaView.induced_slot` must show the
  child's own bound, not only the YAML text.
- #332: the ancestor test must use `is_a` lineage, not "another usage of the same slot". An
  unrelated class with `0..*` beside a class with `0..5` is legal.

## No-gos

- No read-by-IRI route, and no class→`rp_path` map in the TypeScript.
- No `match=` predicate on `on()`, and no payload filter on `hold`.
- No test seam in `Session` or in any production code. `hold` lives on `FakeStore` only.
- No general check that a UML redefinition only narrows. Only the one case LinkML cannot express
  becomes a problem.
- No change to the `InUse` exception's `referrers` tuples (a public field).

---

## What Changes

- Testkit: `FakeStore.hold`. The testkit page `user-manual/test.adoc` gains "aim a fault at the
  request" (`relay.paused()`) and "hold concurrent writes" (`hold`).
- Services model: `Referrer.referrer_rp_path`, `Referrer.referrer_id` (optional; `make
  generate`). `Iris` gains a reverse from an aggregate IRI to its id. The 409 `in-use` problem
  and the referrers listing carry the pair (additive in OpenAPI and TypeScript, RISK-2).
- Converter: a differing cardinality is written per usage, and one new `UmlRule` value is added.
  Regenerated LinkML from existing UML models can change (RISK-1; CHANGELOG "Fixed").

## Capabilities

### Modified Capabilities

- `rp-testkit`: a fault test can keep the relay out, and a test can hold concurrent writes.
- `rp-service-api`: a referrer in the `in-use` problem and in the referrers listing says where to
  read it.
- `rp-uml-import`: a redrawn role keeps its own cardinality bounds.

## Impact

`rdf_persistence/testkit/fakes.py`; `docs/modules/ROOT/pages/user-manual/test.adoc`;
`rdf_persistence/model/technical/collaboration/rp_collaboration_services.yaml` (regenerated);
`rdf_persistence/iris/services/iris.py`; `collaboration/services/referrer_naming.py` and
`collaboration.py`; `api/entrypoints/problems.py` and `service.py` (wiring);
`rdf_persistence_generation/uml/slots.py`, `convert.py`, and the generation model's `UmlRule`
enum (regenerated); `howto/uml-to-linkml.adoc` (the new problem); the CHANGELOG. After the release,
the consumer removes `times=2` (#319), its `store.update` wrapper (#323) and its label-less
referrer display (#320).
