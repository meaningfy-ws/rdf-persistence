<!-- Parents: GitHub issues #83 (atomic commit of several aggregates) and #76 (tenant root by ==); openspec/specs/rp-aggregate-store
     ("Stale writes are refused"); the collaboration EPIC's DEC-8 (moved here). Seed: inputs/seed.md. -->

# EPIC: Commit several aggregates of one tenant atomically

> Shaped 2026-11-12 from issue #83. First in the backlog order (openspec/changes/README.md): the
> collaboration EPIC, cross-aggregate unique keys and aggregate events build on its transaction.
>
> **Developer review 2026-11-13: all recommendations accepted** ("accept all recommendations"):
> all-or-nothing commit with no flag, DEC-4 (limit 500, batch mode now), #76 folded in.

**Golden-thread parent:** issues #83 and #76; capability `rp-aggregate-store` (one named graph per
aggregate; stale writes are refused with a guarded update confirmed by an `ASK`).

## Appetite

**MEDIUM**, two stages: (1) the atomic transaction, the unit of work on it, `remove` and
`version`; (2) the root limit's explicit batch mode. One capability (`rp-aggregate-store`)
reworked in one place (the session's write path); no new store, model or route.

## Why

A use case that changes several aggregates (a form that saves five roots, deleting a root with the
roots that exist only for it, regenerating derived roots) commits them one by one today: a
conflict, crash or lost connection in the middle leaves the tenant half-written, and the consumer
cannot undo it without SPARQL of its own, which it must not write. A consumer's next EPIC (MWB2
v2-02) waits on it, and three toolkit EPICs (collaboration, unique keys, events) need one atomic
write over several graphs.

## Solution outline

The session gains a **transaction**: the writes it collects are sent as **one SPARQL update
request**, which the store applies as one transaction. Its first operation checks every guard of
every change at once (each version token read, each new graph absent) and, only if all hold,
writes a transient marker; every later operation is conditioned on that marker, and the last one
drops it. So either every change applies or none does. The existing single-aggregate writes become
one-change transactions; the unit of work commits all its roots in one.

```python
async with session.transaction() as t:            # one update request when the block exits
    va = await t.replace_graph(a_iri, a_triples, a_version)
    vb = await t.add_graph(b_iri, b_triples)
    await t.remove(c_iri, c_version)
# Conflict(iris=[...]) names every root whose guard failed; nothing was written

uow.add(a); uow.add(b); uow.remove(c)
await uow.commit()          # all three or none
uow.version(a.id)           # the new token, to record which version a process used
await uow.commit(batches=True)   # over the limit: atomic per batch, re-runnable, not atomic overall
```

## Key decisions

- **DEC-1**: One update request per commit, guarded by a marker: a first `INSERT … WHERE` holding
  every guard writes a marker triple with a fresh IRI into the tenant's registry graph; every later
  operation's `WHERE` requires the marker; the last deletes it. Reason: the guards of a replace
  and of an add stop holding once their own graph is written, so they cannot be repeated per
  operation across several aggregates as `REPLACE` does today; the marker evaluates them once,
  before any write. Rejected: repeating every guard in every operation (an add's
  `FILTER NOT EXISTS` turns false after its own insert); a store-side transaction API (Fuseki's
  HTTP transactions are not part of SPARQL 1.1 and other stores lack them, see `second-store`).
- **DEC-2**: One write path. `Session.add_graph`, `replace_graph` and `remove` become one-change
  transactions, so single and multi-aggregate commits share the same templates and tests.
  Rejected: a second, multi-aggregate path beside the old templates (two places to keep correct).
- **DEC-3**: A failed transaction raises `Conflict` whose `iris` names every root whose guard did
  not hold, found by one read after the refused update. The read can race with other writers, so
  the list is a diagnosis, not a guarantee; that nothing was written is the guarantee.
- **DEC-4**: A per-commit limit on the number of roots (default 500, set on the unit of work).
  Over it, `commit()` refuses before writing; `commit(batches=True)` commits batches of at most
  the limit, each atomic, and is **idempotent when re-run**: an add whose root already exists with
  the same triples (bookkeeping excluded) counts as done. Reason: one request of unbounded size
  is a memory and timeout risk on the store. The limit is in roots, not triples, because the
  consumer controls roots; the default is checked against Fuseki in the PLAN.
- **DEC-5** (moved from the collaboration EPIC's DEC-8): the unit of work exposes
  `version(iri)`: the token it read, or after a commit the new one. Rejected: a versioning model
  (deferred by the developer, 2026-11-12: versioning is the store's job).
- **DEC-7** (issue #76, folded in): the session recognises its tenant root whatever the type of
  the IRI given (`str` or `URIRef`), by holding the tenant IRI as a `str` and comparing
  `str(iri)`. Folded here because this change rewrites the same hub (`Session._graph`,
  `_entries`), so one impact gate and one set of session tests cover both. Rejected: its own TINY
  change (a second PR on a CRITICAL symbol right before this one).
- **DEC-6**: The transaction is open for extension inside the toolkit: it holds a list of guard
  patterns and a list of operations. `cross-aggregate-unique-keys` adds key guards and
  `aggregate-events` adds an outbox insert there; the collaboration EPIC adds a presence guard, a remove operation and a state hook (design PD-16). Not public:
  consumers never pass SPARQL.

## Rabbit-holes

- **Pre-checks stay reads before the update.** `replace_graph` reads the stored tracking and the
  registered loaded graphs, and `_check_commit` asks who owns a loaded graph, before the update.
  For N roots these are N reads; batching them into one query is allowed but not required. Their
  races are today's (accepted in `tenant-root-loads`, RISK-4), not new.
- **The same root twice in one transaction** (add then remove, two replaces): refused when it is
  collected, before anything is sent.
- **The tenant root** takes part like any root (its graph is `meta`); the access record in the
  system database is another database and never joins a tenant transaction.
- **Loaded graphs** (`load_graph` puts them before the commit) are outside the transaction as
  today; the commit only registers or drops them.

## No-gos

- No transaction across tenants, or across the tenant and the system database.
- No transaction across the store and the file store (blobs keep today's write order and sweep).
- No long-lived or interactive transactions: nothing is read inside the request; the guards are
  the version tokens the caller read.
- No savepoints, no partial commit inside one transaction, no automatic retry on conflict.
- No change history or versioning model (deferred by the developer, 2026-11-12).
- No new generic HTTP route; the generic API keeps writing one aggregate per request.

---

## What Changes

- `rdf_persistence/services/session.py`: `Session.transaction()` and its `Transaction`
  (`add_graph`, `replace_graph`, `remove`); the templates `ADD`, `REPLACE`, `REMOVE` rebuilt as
  marker-guarded operations; the single-aggregate methods become one-change transactions.
- `rdf_persistence/services/mapper.py`: `UnitOfWork.commit()` is one transaction;
  `UnitOfWork.remove(obj)`, `UnitOfWork.version(iri)`, a `max_roots` limit and
  `commit(batches=True)`.
- `Session` holds the tenant IRI as `str` and compares `str(iri)` (issue #76).
- `rdf_persistence/domain/exceptions.py`: `Conflict.iris`; a `CommitTooLarge` error.
- Tests on the fake store and on Fuseki; docs: the data-flows page, the adoption guide.
- **BREAKING (behaviour):** `UnitOfWork.commit()` no longer leaves earlier roots written when a
  later one conflicts.

## Capabilities

### Modified Capabilities

- `rp-aggregate-store`: several aggregates of one tenant commit atomically; the unit of work
  removes roots, exposes version tokens and bounds the size of a commit.

## Impact

- Public API grows: `Session.transaction`, `UnitOfWork.remove`, `UnitOfWork.version`,
  `commit(batches=…)`, `Conflict.iris`, `CommitTooLarge`. Nothing removed.
- `Session._graph` and the write templates are hubs (GitNexus rated `_graph` CRITICAL on
  2026-11-10): the lead runs impact before stage 1; the store conformance suite and the existing
  session tests are the safety net.
- Unblocks MWB2 v2-02 and the toolkit EPICs `collaboration-and-reference-collections`,
  `cross-aggregate-unique-keys`, `aggregate-events`.

## As built (2026-11-13)

Delivered in #91, #93 and #94, in the two planned stages; the solution outline and every DEC held.
Where the result differs from the text above (each is a recorded decision in design.md, and the
living spec `openspec/specs/rp-aggregate-store/spec.md` says the same):

| Above | As built | Decision |
|---|---|---|
| Appetite: "no new … model" | One metamodel class was added, `CommitMarker` (the marker of DEC-1), generated from LinkML | PD-1 |
| DEC-3: "that nothing was written is the guarantee" | Holds, with one rare exception: a commit that applied and whose every written graph another writer overwrote (or, for removes only, re-added) before the confirming `ASK` raises a false `Conflict`. A re-read shows the true state | PD-4, PD-18h |
| DEC-3: `iris` "names every root whose guard did not hold" | A diagnosis: sorted root IRIs, can miss a root, name one too many, or be empty | PD-4 |
| (not said) | The conflict message names roots in words, no graph IRI or version token (the developer, at acceptance) | PD-20a |
| (not said) | Removing a root another writer already removed is a success (removes-only commit) | PD-17e |
| (not said) | A transaction used after its block ended raises `RuntimeError` | PD-17c |
| DEC-6: "holds a list of guard patterns and a list of operations" | The lists are private; later EPICs extend them from inside `services` | PD-18a |
| DEC-4: the limit | Also: a limit below 1 is refused; `CommitTooLarge` answers HTTP 413; a failed batch keeps its error's type and fields and says how many batches committed; a re-run converges only if the root's own IRI is stable too | PD-19, PD-20 |
| What Changes: `ADD`, `REPLACE`, `REMOVE` rebuilt | `ADD` and the `*_text` builders were removed (no caller); `domain/sparql.py` gained `fragment`/`join`, `domain/iris.py` `is_skolem_of`, `session.py` `without_bookkeeping` | PD-18, PD-20e |
| What Changes: tests on the fake store | `FakeStore` itself changed: atomic per request, an `after_update` hook, requests run one operation at a time (rdflib's parser limit, RDFLib/rdflib#3710) | PD-13, PD-17a |
| RISK-1's conformance case: `CREATE GRAPH` on an existing graph | `LOAD` of a missing file (Fuseki accepts that `CREATE GRAPH`) | PD-13 |
| Measured default | 500 roots: ≈ 4 s, one request of ≈ 2.9 MB on Fuseki; the default holds | PD-10 |

Not built, as the No-gos say: no transaction across tenants or stores, no retry, no new route.
Left open: a unit of work cannot drop a pending add (PD-21a).
