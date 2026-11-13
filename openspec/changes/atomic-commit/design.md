> Derives from: EPIC `atomic-commit` (proposal.md, issue #83). Implements DEC-1 to DEC-7.
> Type: Implementation.

## Context

Every write of an aggregate goes through `Session` (`services/session.py`):

- `add_graph` sends `ADD`, one conditional insert (`FILTER NOT EXISTS` the graph), then
  `ASK_TOKEN` for the new version.
- `replace_graph` reads the stored tracking (`_stored`) and, when `loaded_graphs is None`, the
  registered loaded graphs (`_registered_loaded`); it sends `REPLACE`, five operations each
  repeating `_GUARD` (`GRAPH $graph { $graph $p_version $old }`), ordered so the guard holds until
  the last one drops the old version triple; then `ASK_TOKEN`.
- `remove` sends `REMOVE`, three guarded operations, then `ASK_ANY` (the graph must be empty).
- `_check_commit` refuses IRIs the policy does not mint and loaded graphs another root owns
  (`OWNED_ELSEWHERE`, a read before the update).

`UnitOfWork.commit` (`services/mapper.py`) calls those methods once per dirty root, so a conflict
on the third root leaves the first two written. Callers of the three session methods:
`services/aggregates.py` (generic API), `services/tenancy.py` (tenant root and access records on
the system database), `services/mapper.py` (`UnitOfWork`), `services/file_removal.py`
(`remove_with_files`, single-root `remove`; unchanged by PD-5), tests and the e2e app. GitNexus
impact (2026-11-13): `_graph` CRITICAL, `add_graph`/`replace_graph`/`UnitOfWork.commit` HIGH, as
RISK-3 expects; the developer said proceed.

Repeating one root's guard in every operation works because an operation never invalidates its own
guard before the last step. Across several roots it does not: once root B's graph is inserted, B's
`FILTER NOT EXISTS` guard is false for every later operation, and once A's old version triple is
dropped, A's guard is false. Hence the marker (DEC-1).

## Goals / Non-Goals

**Goals:** the requirements of `specs/rp-aggregate-store/spec.md`: several aggregates commit
atomically; the unit of work removes roots and exposes version tokens; a commit has a size limit
and an explicit batch mode; stale writes are refused (modified wording).

**Non-goals:** the EPIC's No-gos; batching the pre-check reads into one query (allowed, not
required); any change to listings, loads, the sweeps' logic or the HTTP routes.

## Decisions

- **PD-1** (DEC-1): The marker is a metamodel class, `CommitMarker` in `model/rp_core.yaml`
  (`class_uri: rp:CommitMarker`, slots `id` and `started_at`, a datetime), generated like
  `PendingLoad`; `vocabulary.py` gains `STARTED_AT = predicate("started_at")` and the class IRI.
  Its triples: `<urn:uuid:…> rdf:type rp:CommitMarker ; rp:startedAt "…"^^xsd:dateTime` in the
  tenant's registry graph. A fresh `urn:uuid` per transaction, so two transactions never share one.
- **PD-2** (DEC-1): The request is built in three parts, joined with `;\n`:
  1. **Guard**: `INSERT { GRAPH $registry { $marker_triples } } WHERE { $guards }`, where
     `$guards` concatenates, per replaced or removed root, `GRAPH $g_i { $g_i $p_version $old_i }`
     and, per added root, `FILTER NOT EXISTS { GRAPH $g_j { ?s_j ?p_j ?o_j } }` (variables
     suffixed per change so they never join). With no guard at all (impossible: a transaction
     holds at least one change) it would be `{}`; an empty transaction sends nothing.
  2. **Operations**: per change, today's operations with `_GUARD` replaced by
     `_MARKED = GRAPH $registry { $marker a $commit_marker }`. Add: the insert of its triples and
     entries. Replace: `_DROP_UNLISTED, _DROP_ENTRIES, _DROP_GRAPH_BUT_VERSION, _WRITE_NEW,
     _DROP_OLD_VERSION` (the last two may now merge into one `DELETE … INSERT`, but keeping them
     keeps the diff small). Remove: `_DROP_ALL_LOADED, _DROP_ENTRIES, _DROP_GRAPH`. Each change's
     operations are filled with its own terms by the existing `_fill_guarded`/`fill`.
  3. **Release**: `DELETE { GRAPH $registry { $marker ?p ?o } } WHERE { GRAPH $registry { $marker ?p ?o } }`.
- **PD-3** (DEC-1): Confirmation is one `ASK` holding, per add and replace,
  `GRAPH $g { $g $p_version $new }`, and per remove `FILTER NOT EXISTS { GRAPH $g { ?s ?p ?o } }`.
  True → done. False → either nothing was written, or the commit applied and another writer
  changed one of its graphs before the `ASK` (attack, finding 3). `Transaction` diagnoses (PD-4).
- **PD-4** (DEC-3): Diagnosis: one `SELECT ?g ?version WHERE { VALUES ?g { … } OPTIONAL { GRAPH ?g { ?g $p_version ?version } } }`
  over every graph of the transaction. **If any added or replaced graph holds this
  transaction's new token, the commit applied** (all or nothing, so the rest applied too, and a
  later writer changed some graph after it): the transaction returns as a success. A transaction
  of removes only is never a success after a failed `ASK`: it raises `Conflict` naming the removed
  roots whose graph is still present (gate 2). Otherwise nothing was written,
  and a replaced or removed root conflicts when its version
  differs from the one given (or is absent: `NotFound` semantics are folded into the conflict,
  "no longer at version"); an added root conflicts when a version exists. `Conflict.iris` lists
  the root IRIs (not graph IRIs), **sorted** (so `cross-aggregate-unique-keys` and tests can
  compare them without knowing the order of the changes). If the diagnosis finds no
  culprit (a writer restored the old state meanwhile), `Conflict.iris` is empty and the message
  says the transaction lost a race.
- **PD-5** (DEC-2): `Session.transaction()` is an async context manager returning a
  `Transaction` bound to the session. `Transaction.add_graph`, `replace_graph`, `remove` take the
  arguments of today's session methods, run today's pre-checks (`_graph`, `_check_commit`,
  `_stored`, `_registered_loaded`), mint the new version (`uuid4`) and tracking, collect the
  change, and return the new version (remove returns `None`). On a clean exit of the block it
  sends the request (PD-2) and confirms (PD-3); on an exception inside the block it sends nothing.
  A change on a root already collected raises `ValueError` at once; the claim is keyed on the
  graph `self._graph(iri)`, so a `str` and a `URIRef` of one root are the same claim (attack,
  finding 4). `Session.add_graph`,
  `replace_graph` and `remove` become
  `async with self.transaction() as t: return await t.<same>(…)`; `remove` keeps raising
  `NotFound` from its pre-check (`_stored`) as today.
- **PD-6** (DEC-6): `Transaction` keeps `guards: list[str]` and `operations: list[str]` (filled
  SPARQL fragments), appended by the change methods. Later changes add their own fragments from
  inside `services` (key guards, outbox inserts); no public method takes SPARQL.
- **PD-7** (DEC-3): `Conflict` gains `iris: tuple[str, ...] = ()` (keyword, default empty), so
  every existing `raise Conflict(msg)` keeps working; the problem mapping for HTTP is unchanged.
- **PD-8**: `UnitOfWork` changes (`services/mapper.py`):
  - `remove(obj)`: the root must have been read by this unit of work (`ValueError` otherwise, as
    its version is needed); it is dropped from the held objects at commit. A root added (new,
    not read) and then removed raises `ValueError` at `remove`; a read root added then removed
    is removed (remove wins, it leaves `_dirty`); `add` after `remove` raises `ValueError`
    (attack, finding 6).
  - `version(iri) -> str`: from `_versions`; `LookupError(iri)` if absent.
  - `__init__(…, max_roots: int = 500)`; `commit()` counts dirty plus removed roots; over the
    limit it raises `CommitTooLarge` (new, `domain/exceptions.py`, a `PersistenceError`) before
    any read.
  - `commit()`: one `session.transaction()` over all dirty and removed roots, in the order they
    were added; after success, `_versions` holds the new tokens, removed roots are forgotten,
    `_dirty` is cleared. After a `Conflict`, nothing in the unit of work changes, so the caller
    can inspect `Conflict.iris`, re-read and retry with a new unit of work.
- **PD-9** (DEC-4): `commit(batches=True)` slices the same ordered list into batches of
  `max_roots`, each one transaction, committed in order. Per added root of a batch, before the
  batch: if the root already has a graph and its stored triples equal the triples the commit
  would write, it is taken as committed (its stored version goes to `_versions`) and left out of
  the batch; otherwise it stays in and conflicts as usual. The comparison (attack, finding 1):
  drop, from both sides, the statements `payload_triples` adds about the graph IRI (subject the
  graph IRI, predicate in `vocabulary.BOOKKEEPING_PREDICATES`); turn the stored graph's skolem
  IRIs (those starting with `str(graph) + iris.GENID`, i.e. `{graph}/.well-known/genid/…`,
  minted by `iris.skolem_iri`) back into blank nodes; compare with `rdflib.compare.isomorphic`
  against the mapper's triples **before** skolemisation. Parts with
  an explicit IRI compare by that IRI, so idempotence holds only when the re-run builds the same
  part IRIs (anonymous parts, or IRIs derived from the source); `new_part` mints random ones, so
  a re-run of such roots conflicts (safe: nothing is duplicated). The docstring says so.
  Idempotence covers **adds** only; replaces and removes need a re-read.
  After each committed batch, its new tokens go to `_versions`, its roots leave `_dirty`, its
  removed roots are forgotten (attack, finding 5), so the same unit of work can retry the rest
  after a conflict. A conflict stops at that batch, and the batch's exception is re-raised as is
  (same type, so a `KeyConflict` of `cross-aggregate-unique-keys` stays one, same `iris` and
  other fields), its message extended with how many batches were committed. Not atomic overall; the docstring says so.
- **PD-10** (DEC-4): The default limit of 500 roots is checked in stage 2's integration test (a
  500-book commit on Fuseki finishes, and its time is recorded in `develop/index.adoc`'s durations
  table). If it fails or takes over 30 s, the default is lowered to what passes and the change is
  noted here. **Measured (task 2.2, 2026-11-13):** 500 books with two chapters and notes each
  commit in ≈ 4 s (3.8 s, 4.0 s) as one update request of ≈ 2.9 MB; Fuseki takes it with no body
  limit or timeout. The default of 500 holds.
- **PD-11**: The confirmation needs the version token of every changed graph in one `ASK`, so a
  transaction of 500 roots sends a 500-pattern `ASK`. Accepted; measured with PD-10.

- **PD-12** (DEC-7, issue #76): `Session.__init__` stores `self._tenant = str(tenant_iri)`;
  `_graph` and `_entries` compare `str(iri) == self._tenant`. Every other use of `self._tenant`
  already passes it to `Iris` methods, which take `str`. Today's callers (`Tenancy`,
  `ServiceKit.session`) pass `str`, so no behaviour changes for them.
- **PD-13** (attack, finding 2): `FakeStore.update` (`testkit/fakes.py`) applies the request to a
  copy of the dataset and swaps the copy in only if every operation succeeds, so the fake is
  atomic per request like Fuseki. Any failure of the update (rdflib raises a bare `Exception`,
  e.g. "Graph … already exists") is raised as `BadQuery`, as Fuseki's 400 is mapped today.
  `FakeStore` also gains an optional `after_update` hook (an async callable run after a
  successful update, before the method returns), so tests can make another writer act between
  the update and the confirming `ASK` (TC-12; the collaboration EPIC's race tests reuse it).
  Every store parses a whole request before running it, so a parse error proves nothing about
  atomicity; the conformance case makes the **second operation fail at run time**:
  `INSERT DATA {…} ; CREATE GRAPH <g>` with `<g>` already existing (not `SILENT`). If Fuseki does
  not fail that operation, the case uses another run-time failure found during task 1.4 and
  records it here. **Found (task 1.4, 2026-11-13):** Fuseki accepts `CREATE GRAPH` on an existing
  non-empty graph (a no-op, against SPARQL 1.1 Update), and rdflib's `DROP`/`CLEAR`/`ADD`/`MOVE`/
  `COPY` of a missing graph succeed too; so the case is `INSERT DATA {…} ; LOAD
  <file:///nonexistent/none.ttl>`, which both stores fail whole. Fuseki answers 500
  (`StoreUnavailable`), the fake `BadQuery`; the case accepts either and asserts nothing applied.
- **PD-16** (DEC-6, from the collaboration PLAN): the collaboration EPIC extends the transaction
  with internal pieces, added by that EPIC, not this one (its PD-6, PD-8, PD-15, PD-19):
  `_require_present` (the target still has a graph), `_require_match` (a rule member still
  matches), `_DROP_DEPENDENTS` (one extra operation in a remove: the comments and transition
  records about the root) and `_allow_state` (only a transition may change a workflow state).
  This change only keeps `guards` and `operations` open to such additions (PD-6) and its tests
  independent of them.
- **PD-17** (adversarial tester after task 1.2, 2026-11-13; the developer chose the option for
  rdflib, the lead decided the rest):
  - **a** rdflib's update parser recurses once per operation (RecursionError beyond ~50-100
    operations), so `FakeStore` failed a transaction of 15 replaced roots. `FakeStore.update`
    splits the request at top-level `;` (outside IRIs, strings and comments) and runs each
    operation on the dataset copy, still all or nothing (PD-13). Upstream:
    https://github.com/RDFLib/rdflib/issues/3710. Fuseki is not affected.
  - **b** `Conflict.iris` holds `str` root IRIs even when the caller passed a `URIRef` (PD-7).
  - **c** A `Transaction` used after its block ended (committed or raised) raises `RuntimeError`;
    a change is never silently dropped.
  - **d** A change method that raises inside the block, when the caller catches it, leaves no
    claim; the other changes commit on a clean exit. Intended: only collected changes are sent.
  - **e** A removes-only transaction whose root another writer already removed: the guard fails,
    nothing is written, and the confirming `ASK` (graph empty) is true, so it returns as a
    success, as `Session.remove` did before. Idempotent removal; the diagnosis runs only when the
    `ASK` is false.
  - **f** In the diagnosis a removed root whose graph is gone counts as "no longer at version",
    like a changed one (PD-4's "or is absent").
- **PD-18** (stage 1 review, lenses L1, L2, L3, L4+L5, 2026-11-13; decided by the lead).
  Accepted:
  - **a** (L1 W1, L3 W1, L4 W3) `Transaction`'s fragment lists and end flag are private
    (`_guards`, `_operations`, `_ended`); PD-16's additions use internal methods from inside
    `services`. Every `SparqlTerm` comes from `domain/sparql.py`: a joining helper there replaces the
    hand-made `SparqlTerm(" ".join(…))` casts, and the variable suffix of `_ABSENT` goes through
    `fill`/`count` (L1 S1, L5 S2). This amends PD-6 ("keeps `guards`, `operations`").
  - **b** (L1 W2, L4 W1) The `FakeStore` splitter's long-string branches are made disjoint (no
    exponential backtracking); a test bounds the time of an unterminated long string. Its comment
    takes the `shortcut:` form naming rdflib#3710 (L3 S1). Only rdflib's run-time `Exception` and
    `ParseException` become `BadQuery`; `RecursionError` and the fake's own bugs propagate (L1 S3).
    The dataset copy uses `addN` over the quads (L5 S4).
  - **c** (L4 W2) `UnitOfWork` keys its roots by `str(iri)` in `get`, `version` and the rest, as
    PD-12 did for the session.
  - **d** (L4 W4) `_holds` no longer records state; `_collect` records what each change wrote.
  - **e** (L3 W3, L4 W5) `add_text`, `replace_text`, `remove_text` and the `ADD` alias are deleted;
    `tests/unit/services/test_session_updates.py` builds requests from `*_parts` + `request_text`.
  - **f** (L2 W1-W5, S1-S3) Tests: PD-17e (a removed root removed meanwhile is a success); a store
    failure during the confirming `ASK` propagates and the commit applied; the tenant-root
    scenario over both type pairings; the three slow tests shrunk or marked `slow`; `and`-chained
    asserts split, with messages; TC-20 and TC-21 assert exact values; PD-4 reads as PD-17f (a
    removed root whose graph is gone is named), with a test.
  - **g** (L2 W6, W7) `architecture/index.adoc` and `api.adoc` describe the marker guard and the
    transaction. (W8: tasks.md IT-05 now cites PD-13 "Found".)
  - **h** (L4+L5 S6) Error matrix: (a) removes-only whose commit applied and whose root another
    writer re-added before the `ASK` → false `Conflict` (known diagnosis limit, as DEC-3); (b) an
    add whose graph holds triples but no version triple → `Conflict` with empty `iris` and the
    "lost a race" message. Documented, not changed.
  - **i** Small text: the module docstring names the transaction (L3 S2); the `RuntimeError`
    message carries no design id (L5 S5); `UnitOfWork.commit`'s docstring says the order is that of
    first `get` or `add` (L5 S7).

  Rejected: moving the templates and builders to their own module and a `_Change` record with
  `_prepare_*` methods (L3 W2 c, L5 S1): a structural move on a CRITICAL hub with no behaviour
  gain; PD-5 sanctions `Transaction` using the session's helpers, and they stay in one module.
  `Session._rows` (L5 S3): touches existing reads outside this change. An ETag test (L2 S4): the
  token path to the API is unchanged. One table of guards (L2 S5): each guard has positive and
  negative cases already.
- **PD-14** (attack, finding 7): conflict messages change: an add now says
  "… no longer at version …" or "… already exists" per root as found by the diagnosis (PD-4),
  in one message for all roots. Tests that match the old message text are updated; they are
  listed in task 1.2.

- **PD-15** (attack and gate, 2026-11-12): a fresh reviewer scored the first draft 8/10 with seven
  findings (a false "nothing written" after a failed `ASK`; FakeStore not atomic and a parse-error
  test that proves nothing; batch idempotence broken by skolem IRIs; `str`/`URIRef` double claim;
  the unit of work's state after a partial batch; add-then-remove undefined; tests said unchanged
  but some change). All seven are folded into PD-4, PD-5, PD-8, PD-9, PD-13, PD-14 and tasks 1.2,
  1.3, 1.4, 2.1.

## Algorithm / approach

```python
class Transaction:
    async def replace_graph(self, iri, triples, if_version, loaded_graphs=None) -> str:
        graph = self._session._graph(iri); self._claim(iri)              # ValueError if twice
        await self._session._check_commit(iri, loaded_graphs or [])
        _, stored = await self._session._stored(graph)
        loaded = await self._session._registered_loaded(iri) if loaded_graphs is None else loaded_graphs
        version = str(uuid4()); payload = payload_triples(graph, version, tracking(stored), triples)
        self.guards.append(version_guard(graph, if_version, n=len(self._changes)))
        self.operations.append(replace_ops(graph, registry, iri, payload, entries(iri, graph, loaded)))
        self._confirm.append(token_pattern(graph, version))
        return version

    async def _send(self):                                   # on clean exit, if any change
        marker = URIRef(f"urn:uuid:{uuid4()}")
        text = ";\n".join([guard_op(marker, self.guards), *marked(self.operations, marker), release(marker)])
        await store.update(database, text)
        if not await ask(" ".join(self._confirm)):
            await self._diagnose()      # returns if the commit applied (PD-4); raises Conflict otherwise
```

Worked example (toy library; A, B stored at `a1`, `b1`; C new):

| Step | Store |
|---|---|
| `t.replace_graph(A, …, "a1")`, `t.replace_graph(B, …, "b1")`, `t.add_graph(C, …)` | unchanged (collected) |
| Another session replaces B → `b2` | B at `b2` |
| Block exits; guard op: `A at a1` ✓, `B at b1` ✗, `C absent` ✓ → no marker | unchanged |
| Every marked operation matches no row; release deletes nothing | unchanged |
| `ASK` (A at `a2'`, B at `b2'`, C at `c1'`) → false; diagnosis reads A `a1`, B `b2`, C none | — |
| `Conflict("…", iris=("B",))` | A at `a1`, B at `b2`, no C |

Without the concurrent write, the guard op writes the marker, every operation runs, the release
drops the marker, and the `ASK` is true.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Repeat each root's guard in every operation | One guard op and a marker (PD-2) | An add's guard turns false after its own insert |
| Send one request per root inside a "transaction" object | One request for the whole block | Only one request is one store transaction |
| Keep `ADD`/`REPLACE`/`REMOVE` beside the new path | Single-root methods are one-change transactions (PD-5) | Two write paths drift |
| Name a culprit from the failed `ASK` alone | The diagnosis read (PD-4) | The `ASK` only says "not all new tokens"; the read says which root |
| Promise `Conflict.iris` is exact | Document it as a diagnosis (DEC-3) | It is read after the refusal and can race |
| Accept raw SPARQL from callers for the guard/operation lists | Internal fragments only (PD-6) | Consumers never pass SPARQL (rp-aggregate-store) |
| Put the marker in a graph of its own | The tenant's registry graph | One graph fewer for the sweeps and the conformance suite to know |
| Read inside the request | Version tokens the caller read are the guards | No interactive transactions (No-gos) |

## Error matrix

| Input | Result |
|---|---|
| A replaced root changed meanwhile | `Conflict(iris=(A,))`, nothing written |
| An added root already exists | `Conflict(iris=(B,))`, nothing written |
| A removed root changed meanwhile | `Conflict(iris=(C,))`, nothing written |
| A replaced or removed root has no graph at collection time | `NotFound` from the pre-check, nothing sent |
| The same IRI given twice to one transaction | `ValueError` at the second call, nothing sent |
| An IRI the policy does not mint, or a loaded graph owned elsewhere | `InvalidIri` at collection, nothing sent (today's `_check_commit`) |
| An exception inside the `async with` block | nothing sent, the exception propagates |
| The store fails during the update | the store's error (`StoreUnavailable`, `DatabaseGone`) unchanged; nothing visible (one transaction) |
| The store fails after the update, during the `ASK` | the store's error; the commit may have applied. Same as today for one root; the caller re-reads |
| Two transactions race on the same root | the store serialises the requests; the second's guard fails → `Conflict` |
| `UnitOfWork.remove` of a root it did not read | `ValueError` |
| `UnitOfWork.version` of an unknown IRI | `LookupError` naming it |
| 501 dirty roots, limit 500, no batches | `CommitTooLarge` naming 501 and 500, before any read |
| Batch mode, a conflict in batch 2 of 3 | batch 1 stays committed; `Conflict` names the root and says 1 batch committed |
| Batch mode re-run, an added root exists with other triples | that root conflicts (it was not this import's) |
| A transaction on the tenant root and a book | both in one request; the root's graph is `meta`, no `Aggregate` entry (unchanged `_entries`) |
| Empty transaction (no change) | nothing sent, no error |
| The commit applied, then another writer changed one of its graphs before the `ASK` | success (PD-4: some graph holds this transaction's new token) |
| Removes only; another writer changed a removed root first | `ASK` fails; `Conflict(iris=(that root,))`; nothing written (never a success, PD-4) |
| The commit applied, then **every** added or replaced graph was overwritten by others before the `ASK` | false `Conflict` (known diagnosis limit, DEC-3); the data is consistent; a re-read shows the others' versions |
| Removes only; the commit applied, then another writer re-added a removed root before the `ASK` | false `Conflict` naming it (known diagnosis limit, PD-18h); a re-read shows the other writer's root, which a blind retry must not remove |
| An add whose graph holds triples but no version triple | `Conflict` with empty `iris` and the "lost a race" message (PD-18h) |
| Removes only; another writer already removed the root | success, nothing written (idempotent removal, PD-17e) |
| A `str` and a `URIRef` of one root in one transaction | `ValueError` (claim keyed on the graph, PD-5) |
| Batch re-run of roots whose parts got random IRIs from `new_part` | those roots conflict; nothing duplicated (PD-9) |

## Risks / Trade-offs

- **RISK-1** — a store that does not apply one multi-operation request as one transaction would
  let a crash leave a half-applied commit and a stray marker (low on Fuseki/TDB2, which the
  existing `REPLACE` already relies on; high on an unknown store). Mitigation: `second-store`'s
  capability descriptor states it; the store conformance suite gains a case (an update request
  whose second operation fails at run time leaves the first unapplied, PD-13) that every adapter
  must pass.
- **RISK-2** — large requests (500 roots × their triples) hit a store or proxy body limit or a
  timeout (medium; medium). Mitigation: PD-10 measures; the limit is a constructor argument.
- **RISK-3** — `Session._graph` and the templates are hubs (CRITICAL in GitNexus). A regression
  breaks every write (low with tests; high). Mitigation: stage 1 keeps every existing session,
  mapper, tenancy, aggregates and integration test green; only the tests listed under task 1.2 (PD-14 message text, TC-28) change; the conformance cases run on
  Fuseki before the PR.
- **RISK-4** — the pre-check reads are N round trips for N roots (certain; low for forms, medium
  for 500-root batches). Accepted; batching the reads into one `VALUES` query is a later
  optimisation if PD-10's timing calls for it.
- **RISK-5** — batch-mode idempotence compares graphs with `isomorphic`, which is costly on large
  graphs (low; low). Accepted: only for added roots that already exist, i.e. only on a re-run.
- **Assumption** — nothing else in the registry is typed `rp:CommitMarker`, and the sweeps ignore
  subjects they do not know. Checked 2026-11-12: `tenant_sweep.py` reads `PendingLoad` markers
  and entries by kind; a stray marker (RISK-1 only) is inert.

## Open Questions

None blocking. For the developer to confirm (each decided by the lead, 2026-11-12):

- Default limit 500 roots (PD-10 may lower it).
- Batch mode built now rather than waiting for a consumer to hit the limit.
- The behaviour change of `UnitOfWork.commit()` (all or nothing) ships without a flag.
