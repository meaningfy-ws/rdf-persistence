# Seeds: consumer-test-gaps (secondary, never groomed)

The four issues as filed, verbatim (read 2026-11-24 with `gh issue view`).

## #319: testkit: FakeStore.on faults are taken by the event relay, not by the request's write

## What falls short

`testkit.fakes` `FakeStore.on(operation, error, times=1, after=0)` arms a failure by **call index** across every caller of `operation`. A consumer service built with the kit starts the event relay with each request; the relay also calls `update`. When the request's own write is preceded by an `await` that yields to the loop (for example `asyncio.to_thread` for a content check), the relay may take the armed failure first, so "the data store fails the next write" is not deterministic: the request then answers 201/204 instead of 503.

## Reproduction (consumer side)

1. A service over the testkit's fakes (`fake_session` / the kit with `FakeStore`).
2. A route that does `await asyncio.to_thread(check, data)` and then writes through the session.
3. `store.on("update", StoreUnavailable("down"))`, then call the route.
4. Depending on scheduling, the relay's `update` raises and the route's write succeeds.

## What we need

A way to aim a fault at the request's write and not at the relay's, e.g. `on(..., match=lambda payload: ...)` (a predicate over the payload the fake already records in `sent`), or a switch to keep the relay out of a test.

## What the consumer does meanwhile

Mapping Workbench 2 arms the fault with `times=2` in its feature step and points to this issue; it removes that once a targeted fault exists.


## #320: in-use referrers carry no rp_path, so a client cannot read the referrer's label

## What falls short

The `in-use` problem (#201) names each referrer by `referrer` (IRI), `referrer_class` and `referrer_slot`. A client that wants to show the referrer's label must read it through the generic `GET {tenant_segment}/{t}/{rp_path}/{id}`, but nothing in the answer, nor in the generated TypeScript, maps a referrer (or its class) to its `rp_path`, and the API has no read by IRI. A client can only guess the `rp_path` from the IRI's class segment, which ADR-style IRI policies do not promise.

## Reproduction

1. A consumer with two aggregate classes, A pointing to B.
2. Delete B through a route that passes `readable=`; the answer is 409 `in-use` with `referrers: [{referrer: "<A IRI>", referrer_class: "<A class>", referrer_slot: "<slot>"}]`.
3. From that body alone, the client cannot form the generic `GET` of A.

## What we need

Either `rp_path` (and the bare id) on each referrer of the `in-use` problem, or a generic read by IRI within a tenant (`GET {tenant_segment}/{t}/objects?iri=…` or similar, access-checked like the class routes), or the class → `rp_path` map in the generated TypeScript.

## What the consumer does meanwhile

Mapping Workbench 2 shows each referrer's IRI (and class) without its label, and adds the label when one of the above exists. No guessing.


## #323: testkit: no way to hold a commit for a deterministic concurrent-write scenario

## What falls short

A consumer that wants to prove "two concurrent writes to one root: one commits, the other gets `Conflict`" over the testkit's fakes has no way to hold a commit until the second writer has read. It must replace `FakeStore.update` with a wrapper that matches the update's SPARQL text and waits, which ties the test to the toolkit's SPARQL and to the fake's internals.

## Reproduction (consumer side)

1. A service over the testkit's fakes; a route that reads the tenant root and replaces it at the version read (one `session.transaction()`).
2. Fire two requests at once. Without a barrier the first usually commits before the second reads, so the conflict path is not exercised deterministically.
3. The only way today is to monkeypatch `service.store.update` and hold updates whose text contains a given predicate until two are waiting.

## What we need

A testkit facility to hold commits, e.g. `FakeStore.hold("update", until=2)` (release when N calls wait) or a barrier/latch on commit, so a consumer can write a deterministic concurrency scenario without touching the fake's methods or SPARQL.

## What the consumer does meanwhile

Mapping Workbench 2's scope feature wraps `store.update` for that one scenario (design D-13 c) and removes the wrapper once a hold exists. Related: #319 (faults counted across the relay and the request).


## #332: UML converter: a narrowed minimum/maximum cardinality is inherited from the parent usage

Found in review of #330 (`consumer-gap-fixes`, #304), outside that EPIC's No-gos.

`usage_of` (`rdf_persistence_generation/uml/slots.py`) now writes a differing `required`/`multivalued` explicitly (D-5), but the cardinality limits still go through `_shape_kwargs`, which skips `None`. A subclass that narrows an inherited `2..*` role to `1` makes `minimum_cardinality` differ, writes nothing for its own `None`, and so inherits the parent usage's `2`; the same holds for `maximum_cardinality`.

Reproduction: abstract `A` with `p 2..*` to `V`; `B is_a A` with `p 1` to `W is_a V`; `SchemaView.induced_slot("p", "B").minimum_cardinality` is 2.

Candidate home: `converter-hardening`.
