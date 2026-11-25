# Design: consumer-test-gaps

> Derives from: EPIC `consumer-test-gaps` (`proposal.md`: #319, #320, #323, #332). Its DEC-1 to
> DEC-6 are cited here, not restated. The delivery decisions below are D-n.

## Context

The code facts the plan rests on were read on `develop` at `1f2687bc`:

- **Faults.** `_Instrumented.on` (`testkit/fakes.py` l.67) stores a fault under a call index,
  `len(sent[operation]) + after`. `_enter` (l.82) appends the payload to `sent`, then pops and
  raises the fault for that index. It is synchronous, and every `FakeStore` operation calls it
  first. `FakeStore.update` (l.170) runs synchronously after `_enter` until the optional
  `after_update` hook.
- **The relay.** `Relay.run` (`events/services/relay.py` l.113) waits for a wake or an interval,
  then calls `run_once`, which takes `self._lock`. `Relay.paused()` (l.134) holds that same lock,
  so no round starts while the block is open. A round's `Session.mark_relayed` → `_mark`
  (`session.py` l.987) is one `store.update`, and only the relay calls it. The kit wakes the
  relay on every commit (`kit.py` l.261). `service.py` l.209 starts `kit.relay.run()` in the
  app's lifespan. The toy service's client (`tests/toy_service.py` l.209, `httpx.ASGITransport`)
  does **not** run the lifespan. A test that needs a live relay enters
  `app.router.lifespan_context(app)` itself, as `tests/feature/test_events.py` l.258 does.
- **Commits.** A commit is one `store.update` (`session.py` l.1619), then an ASK. A failed version
  guard leads to a `Conflict`, answered 409 `conflict`. `StoreUnavailable` is answered 503 with the
  slug `unavailable` (`problems.py` l.83, l.124). The documents' POST and PUT run their SHACL check
  in `anyio.to_thread` before writing (`api/services/documents.py` l.228, l.472): this is #319's
  "await before the write".
- **Referrers.** `InUse.referrers` holds `(IRI, class name, slot name)` tuples
  (`core/domain/exceptions.py` l.70-93). `in_use_problem` (`api/entrypoints/problems.py` l.174)
  turns them into the generated `Referrer`. `install_problem_handlers(app, base)` (l.238) is
  called from `service.py` l.176, where the kit exists, and from `tests/unit/api/test_problems.py`
  l.90. `Collaboration._listed` (`collaboration.py` l.244) builds the referrers listing's
  `Referrer` items. `Collaboration` already holds `_view` and `_iris`. Importing the iris and schema
  themes from `collaboration` is allowed by `.importlinter` (`themes-ordered`). `Referrer` is
  defined in `model/technical/collaboration/rp_collaboration_services.yaml`, and the 409 problem
  and the listing share it. `Documents.aggregates` (`api/services/documents.py` l.160) maps each
  served `rp_path` to its class, read from the `rp_path` annotation of `served_roots`.
  `Iris._aggregate_re` (`iris.py` l.319) is the compiled aggregate template, with named groups
  that include `id` and `rp_path`. Every policy's aggregate template must end in `{id}`, so the
  `id` group always exists. `Iris` has no public reverse from an IRI to its id; `is_aggregate`
  (l.573) only matches. `referrer_naming.py` already holds the helpers that `Collaboration` and
  the removal guard share. Referrer rows are roots, and the mapper writes only the concrete class
  type, so a root of several classes is rare.
- **Cardinality.** `_bounds` (`uml/slots.py` l.88) sets `minimum_cardinality` only when the
  lower bound is above 1, and `maximum_cardinality` only when the upper bound is finite and above
  1; otherwise it leaves them `None`. `differing_fields` compares `LIMIT_FIELDS`, which include
  both cardinalities. `usage_of` (l.234) writes `_shape_kwargs(shape, differing)`, which skips
  `None` and `False`; #330 added the explicit `required`/`multivalued` (consumer-gap-fixes D-5).
  `share` (l.445) has `ctx` and every usage of one name, but no `is_a`. `classes.parents(ctx,
  model)` (`uml/classes.py` l.277) gives each class's parent label by object id; `convert.py`'s
  `_lay_out` holds it as `parent_of` where it calls `share` (l.398). Converter problems are
  `UmlRule` values, an enum in `rdf_persistence_generation/model/rp_generation.yaml`, and any
  problem fails the run. UML generalisations give only `is_a`: toolkit-drawn parents are split
  off before `share`, so the lineage needs no mixins. In the targets, `minimum_cardinality: 0`
  survives `induced_slot` (linkml-runtime 1.12.1, `is_empty(0)` is false). The repository's
  Pydantic template applies cardinalities only to multivalued slots, and shaclgen ignores a falsy
  minimum and adds no constraint.

## Goals / Non-Goals

**Goals:** each issue's scenarios as tests that fail first; the consumer's three workarounds made
unnecessary. **Non-Goals:** the EPIC's No-gos.

## Decisions

- **D-1 (DEC-1):** no code for #319. The page `user-manual/test.adoc` gains a section "Aim a fault
  at the request". It shows `async with kit.relay.paused():` around the call, says why (the
  relay's mark is an `update`), and says that a wake-up during the block makes one round after
  it. The feature test (E1) is the proof.
- **D-2 (DEC-2):** the `hold` contract.
  - Signature: `FakeStore.hold(operation: str, until: int, timeout: float = 5.0)`, an
    `asynccontextmanager`. An unknown `operation` raises `ValueError` (`_known`). `until < 1`
    raises `ValueError`. A second `hold` on the same operation while one is open raises
    `RuntimeError`.
  - Inside the block, each of the first `until` calls of `operation` waits before `_enter`. When
    the `until`-th arrives, all of them are released together, in arrival order. Calls after the
    `until`-th do not wait.
  - If the hold has not filled `timeout` seconds after its first waiter arrived, the waiters are
    released in arrival order (they run normally).
  - On exit, every call still waiting is released in arrival order, whatever the reason for the
    exit. Only a clean exit then checks the count: a hold that saw fewer than `until` calls raises
    `AssertionError(f"hold({operation!r}, until={until}) saw {n} call(s)")`. An exit by an
    exception or a cancellation re-raises that exception and never masks it with the
    `AssertionError`.
  - A waiting call records nothing in `sent` and takes no fault until it is released, so `on` and
    `sent` see calls in release order.
  - The waiting point is one `async` method on `FakeStore`, awaited first by each of its `async`
    operations. `_Instrumented` stays synchronous.
- **D-3 (DEC-2, release order):** each waiter, the `until`-th included, awaits **its own future**,
  kept in a list in arrival order. The release resolves them one at a time, in that order, and
  yields (`await asyncio.sleep(0)`) after each, so the released call runs `_enter` and its write
  before the next future is resolved. Each released `update` runs synchronously to its end,
  because `FakeStore.update` does not await between `_enter` and its write. So the first arrival
  commits first, and the second's version guard sees the new version. Rejected: one shared
  `asyncio.Event`. `Event.wait()` returns without yielding when the event is already set, so the
  `until`-th caller, which sets it, would write first.
- **D-4 (DEC-3):** `Referrer` gains `referrer_rp_path` (`slot_uri: rp:referrerRpPath`, string)
  and `referrer_id` (`slot_uri: rp:referrerId`, string), both optional, in
  `rp_collaboration_services.yaml`. Then `make generate`.
- **D-5 (DEC-3):** `Iris.aggregate_id_of(iri: str) -> str | None` returns the `id` group of
  `_aggregate_re.fullmatch(iri)`, or `None`. It does not check the tenant: the IRI comes from the
  tenant's own referrer read.
- **D-6 (DEC-3):** one helper, `located(view, iris, class_name, iri) -> tuple[str, str] | None` in
  `collaboration/services/referrer_naming.py`, gives `(rp_path, id)`. The `rp_path` is the
  class's `rp_path` annotation when the class is a served root (the test `Documents.aggregates`
  uses). The id comes from D-5. If either is missing, it returns `None`, and neither field is set.
  - `Collaboration._listed` stays a static method and takes a `locate(class_name, iri)` callable,
    which `Collaboration.referrers` passes as `partial(located, self._view, self._iris)`. It fills
    both fields.
  - `install_problem_handlers(app, base, locate=None)` takes a `locate(class_name, iri)` callable.
    `service.py` passes `partial(located, kit.view, kit.iris)`.
  - `in_use_problem` fills both fields through `locate`. With no `locate` (a direct caller), the
    fields stay unset, as today.
- **D-7 (DEC-4):** `usage_of` writes each differing cardinality from the usage's own
  multiplicity. The bounds are derived from the shape; the shape gains no new field. Two helpers
  in `slots.py`, `own_minimum(shape)` and `own_maximum(shape)`, give:
  - minimum: `shape.minimum_cardinality` if set, otherwise `1` if `required`, otherwise `0`;
  - maximum: `shape.maximum_cardinality` if set, otherwise `1` if not `multivalued`, otherwise
    `None` (unbounded, not written).

  A field that does not differ writes nothing, as today (E19). `0..0` (or `0`) already parses
  into the same shape as `0..1`, so its maximum is derived as 1. That is a parse limit that
  predates this change, and it is recorded as E22, not fixed.
- **D-8 (DEC-4, DEC-5):** `share` takes the id-keyed `parent_of: Mapping[int, str]` (object id →
  parent label) that `_lay_out` already holds, and walks the lineage by label through a
  label → object id map built from **every converted element** `_lay_out` holds, not from the
  usages' holders: a middle class with no attributes holds no usage but is still in the lineage
  (E23). For each usage whose `own_maximum` is
  `None` while the maximum differs, it walks the holder's `is_a` lineage, nearest first. When an
  ancestor's usage of the same name has a **finite `own_maximum`** (the derived bound of D-7, not
  the stored `shape.maximum_cardinality`, which is `None` for a single-valued `0..1`), it adds
  `ctx.findings.problem(UmlRule.CARDINALITY_UNBOUNDED, "<Class>.<slot>", …)`. The message names
  the ancestor and its bound and says "an unbounded role cannot redraw a bounded one: bound the
  role or unbind the ancestor's". `cardinality_unbounded` is a new value of the `UmlRule` enum
  (with `make generate`), and the rule table in `howto/uml-to-linkml.adoc` gains its row.

## Anti-patterns

| Don't | Why | Instead |
|---|---|---|
| Hold `update` with the relay running | A relay mark fills the hold, so the test is flaky (RISK-3) | `async with kit.relay.paused(), store.hold(...)` |
| Release a hold with one shared `asyncio.Event` | The `until`-th caller never yields and writes first (D-3) | One future per waiter, resolved in order |
| Test an ancestor's stored `maximum_cardinality` | It is `None` for a single-valued `0..1`, so the problem is missed (E21) | Compare `own_maximum` (D-7) |
| Compute `rp_path` and id separately in the problem handler and the listing | The two answers drift | The one helper `located` (D-6) |
| Match SPARQL text in a test to find "the request's update" | It ties tests to the toolkit's SPARQL (#323) | `relay.paused()` plus `hold` |

## Algorithm / approach

### Stage 1: testkit (#319, #323)

1. Tests first.
   - Unit, `tests/unit/testkit/test_fake_store.py`: E3 to E8, with `asyncio.gather` of two
     `store.update` calls under `hold`.
   - Feature, `tests/feature/testkit_faults.feature` with `test_testkit_faults.py`, over the toy
     service (`tests/toy_service.py`): E1 and E2. The test enters
     `app.router.lifespan_context(app)` itself, as `tests/feature/test_events.py` l.258 does,
     because the toy's `ASGITransport` client skips the lifespan; only then is the relay live. The
     write route is the documents' POST, whose SHACL check runs in `anyio.to_thread` before the
     write.
2. `hold` (D-2, D-3), then the two `test.adoc` sections (D-1), whose example code is the feature
   test's.

Worked example (E2):

```python
async with kit.relay.paused(), store.hold("update", until=2):
    a, b = await asyncio.gather(client.put(url, json=v1, headers=h), client.put(url, json=v1b, headers=h))
assert sorted([a.status_code, b.status_code]) == [200, 409]
```

### Stage 2: API (#320)

1. `Referrer` slots (D-4), then `make generate`. The golden TypeScript fixtures change (RISK-2).
2. Tests first.
   - Unit, `tests/unit/iris/`: `aggregate_id_of` for E12.
   - Unit, a new `tests/unit/collaboration/test_referrer_location.py`: `located` for E10, E11 and
     E13.
   - Unit, `tests/unit/api/test_delete_in_use.py`: E9 and E14.
   - Unit, `tests/unit/collaboration/test_collaboration_readable_referrers.py`: E9 for the listing.
3. `aggregate_id_of`, `located`, `_listed`, `in_use_problem`, and the wiring in `service.py`
   (D-5, D-6).

Worked example: a `Loan` at `…/loans/42` refers to `Book` `b`. `DELETE …/books/b` answers `409`
with `referrers: [{referrer: "<…/loans/42>", referrer_class: "Loan", referrer_slot: "book",
referrer_rp_path: "loans", referrer_id: "42"}]`, and `GET …/loans/42` returns 200.

### Stage 3: generator (#332)

1. Tests first, in `tests/generator/unit/test_uml_rules.py` beside #330's E1 to E3: E15 to E20.
   Each is checked through `SchemaView.induced_slot` as well as through the YAML.
2. `usage_of` (D-7), `share` with `parents`, and the problem (D-8); `UmlRule` in the generation
   model, then `make generate`. Regenerate the toy fixtures. The golden diff may hold only explicit
   cardinalities on slots whose usages differ (RISK-1). The CHANGELOG gets a "Fixed" entry naming
   the pattern.

Worked example (E15): abstract `A` with `p 2..*` to `V`; `B is_a A` with `p 1` to `W is_a V`.
Before, `B.slot_usage.p` is `{range: W, required: true, multivalued: false}` and the induced
minimum is 2. After, it is `{range: W, required: true, multivalued: false, minimum_cardinality:
1}` and the induced minimum is 1.

## Error matrix

| Id | Input / state | Expected |
|---|---|---|
| E1 | Lifespan entered; inside `kit.relay.paused()`, a commit (so an activity is pending and the relay woken; the test asserts it is still pending), then `store.on("update", StoreUnavailable("down"))` and a documents POST (its SHACL check runs in `anyio.to_thread` before the write) | 503 `unavailable` on each of 20 runs; after the block the activity is relayed (`relayed_at` set) |
| E2 | `relay.paused()` and `hold("update", until=2)`; two concurrent replaces of one root at the same version | One 2xx and one 409 `conflict`; the stored version is the winner's |
| E3 | `hold("update", until=2)`; two `update` calls through `gather` | The first call does not apply before the second arrives; both apply, in arrival order: the `until`-th (the second) call applies last |
| E4 | `hold("update", until=2, timeout=0.1)`; one call only | That call completes after about 0.1 s; leaving the block raises `AssertionError` naming the operation, `until=2` and `1 call` |
| E4b | `hold("update", until=2)`; one call waiting, started as a separate task (`asyncio.create_task`) outside the body's own awaits; the block body raises `KeyError` (or is cancelled) | The waiting task is released and completes; the block re-raises the `KeyError` (or `CancelledError`), not an `AssertionError`. A waiting call awaited inside the cancelled body is cancelled with it, which is asyncio's rule, not the hold's |
| E5 | `hold("updte", until=2)` / `hold("update", until=0)` | `ValueError`, before any call waits |
| E6 | `hold("update", until=1)` nested in another open `hold("update", …)` | `RuntimeError` |
| E7 | `hold("update", until=2)`; three calls | The third does not wait |
| E8 | `on("update", err)` armed before a `hold("update", until=2)` with two calls | The fault goes to the first call released; `sent` lists the payloads in release order |
| E9 | `DELETE` of a root referred to by an aggregate of a served class, `readable=` passed; then `GET …/referrers` of the same root | Each referrer carries `referrer_rp_path` and `referrer_id`; `GET {tenant_segment}/{t}/{rp_path}/{id}` built from them returns 200 for that referrer |
| E10 | A referrer row whose class is not a served root (a mixin, or an IRI the schema does not know) | Neither field is set; `referrer`, `referrer_class` and `referrer_slot` are unchanged |
| E11 | A served class, but an IRI that does not match the aggregate template | Neither field is set |
| E12 | `aggregate_id_of` on a policy-minted aggregate IRI; on a tenant root; on a foreign IRI | The minted id; `None`; `None` |
| E13 | A root of two classes, one served, one not | Two rows; only the served class's row carries the pair |
| E14 | An unfiltered `InUse` (no `readable`) | Unchanged: `referrers: []` and every referrer counted in `hidden_count` |
| E15 | `A p 2..*`, `B is_a A` with `p 1` | `B` writes `minimum_cardinality: 1`; the induced minimum is 1 |
| E16 | `A p 0..5`, `B is_a A` with `p 0..1` | `B` writes `maximum_cardinality: 1`; the induced maximum is 1 |
| E17 | `A p 0..5`, `B is_a A` with `p 0..*` | Problem `cardinality_unbounded` on `B.p`; the run fails |
| E18 | `A p 2..*`, `B is_a A` with `p 0..*` | `B` writes `minimum_cardinality: 0`; the induced minimum is 0; Pydantic, SHACL and JSON Schema accept it |
| E19 | Every usage agrees on both cardinalities | No cardinality in any `slot_usage` (unchanged) |
| E20 | `A p 0..5` and an unrelated class `C` (no `is_a` to `A`) with `p 0..*` | No problem; `C` writes nothing for the maximum, and `A` writes `maximum_cardinality: 5` |
| E21 | `A p 0..1`, `B is_a A` with `p 0..*`, and an unrelated `D p 0..3` (so the maximum differs) | Problem `cardinality_unbounded` on `B.p`: `A`'s derived maximum is 1, though its stored one is `None` |
| E23 | `A p 0..5`, `M is_a A` with no attributes, `B is_a M` with `p 0..*` | Problem `cardinality_unbounded` on `B.p`: the walk passes through `M` |
| E22 | `A p 0..0` beside `B p 0..3` | `A` writes `maximum_cardinality: 1` (unchanged parse limit: `0..0` reads as `0..1`); recorded, not fixed (D-7) |

## Risks

- **RISK-1** (likely, low impact): #332 changes the LinkML that existing UML models generate.
  Explicit cardinalities appear on usages of slots whose cardinalities differ, and a consumer's
  shape snapshot shows a diff on regeneration. Accepted: CHANGELOG "Fixed" names the pattern and
  says to regenerate (owner, round 2).
- **RISK-2** (certain, low impact): two optional fields on `Referrer` change the OpenAPI document
  and the generated TypeScript, and our golden fixtures move. The change is additive, so it is
  accepted (owner, round 2).
- **RISK-3** (possible, medium impact): a consumer holds `update` with the relay running, so a
  relay mark fills the hold and the test is flaky. Mitigation: the docstring and the page say that
  `hold` belongs inside `relay.paused()` (owner, round 2).
- **RISK-4** (unlikely, high impact for the one consumer it hits): a consumer's model already has
  an unbounded role under a bounded ancestor, and its conversion now fails (DEC-5). Mitigation:
  the problem message says how to fix the model (bound the child or unbound the ancestor), and the
  CHANGELOG names it.
- **RISK-5** (possible, medium impact): E1 passes for the wrong reason, because no relay round was
  due, or because the relay relayed the earlier commit before the block opened. Mitigation: E1
  makes its commit **inside** `paused()`, asserts the activity is still pending before arming the
  fault, and repeats 20 times. A control step without `paused()` is not asserted, since it is the
  non-deterministic case.

## Open questions

None. Both rounds answered every concern (`inputs/qa.md`).

## Delivery decisions

- **D-9 (DEC-6, lead, 2026-11-24):** the three stages are built in parallel, one builder and one
  worktree each (`.worktrees/ctg-1` to `ctg-3`), because they share no code. Their PRs still open,
  are reviewed and merge in DEC-6's order (testkit, API, generator), each rebased on `develop`
  before it opens (P-0002); the shared `CHANGELOG.md` and `scenario-map.csv` conflicts are
  resolved at that rebase. Three full suites at once on a machine other sessions also loaded
  (load ≈ 50) never finished a builder's task gate, so the lead ran the gates one stage at a time
  instead (T1 for each stage).
- **D-10 (lead):** `make refresh-map` exits non-zero on `develop` already: 84 collected tests have
  no row, none of this change's. Each stage adds rows for its own tests only; the 84 are left to a
  follow-up. The refresh also drops four rows whose tests no longer exist and moves others; those
  hunks are left out, so a stage's map diff holds only its own rows and the stages rebase cleanly.
- **D-11 (stage-1 review W1, re-labelled Critical: it breaks a SHALL of `rp-testkit`):** a hold
  fails on a clean exit unless it **filled**, that is, its `until`-th call arrived before the
  timeout released it. A call that arrives after the timeout still runs at once, but no longer
  counts towards filling. The message names the calls seen before the release. E4 gains a case
  where the second call arrives after the timeout.
- **D-12 (stage-1 review W2, re-labelled Critical: E1's THEN could not fail):** E1 no longer calls
  `relay.run_once()` after the block; it waits with `testkit.wait_until_async` until the live,
  woken relay has set `relayed_at`. The "Aim a fault" example on `user-manual/test.adoc` does the
  same, and its text and example agree.
- **D-13 (stage 2, builder, confirmed by the lead):** task 2.4 named `reference/http-api.adoc`, but
  that page holds no text on the `in-use` problem or the referrers listing. The two fields are
  documented where those already are: `architecture/api.adoc` (the 409 `in-use` members),
  `howto/reverse-references.adoc` (the `Referrer` item) and `user-manual/store-and-read.adoc` (the
  example 409 body). The item is built by one helper, `referrer_item`, beside `located` in
  `referrer_naming.py`, so the problem and the listing cannot drift (D-6).
