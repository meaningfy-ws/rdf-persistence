> Derives from: EPIC `cross-aggregate-unique-keys` (proposal.md). Implements DEC-1 to DEC-6.
> Depends on: change `atomic-commit` (issue #83), merged first. Type: Implementation.

## Context

v1 reads `unique_keys` in one place, `services/schema_structure.py` (`_keys_of`, `keyed_slots`):
a key declared on a class is enforced on every multivalued slot holding objects of that class,
inside one aggregate, by a generated validator (`generation/extensions/pydantic_validators.py`)
and a SHACL SPARQL constraint (`generation/extensions/shacl_constraints.py`). The toolkit's only
key is `Grant.grant_key` (`model/rp_access.yaml`). The hard check (`generation/checks/hard.py`,
`_unique_key_problems`) only checks that a key name is an identifier. The conformance suite
(`testkit/conformance.py`, `_CLASS_KINDS`) marks a class declaring `unique_keys` as using
`UNIQUE_KEYS`.

A key on an aggregate root has no meaning today: no slot owns a root, so `keyed_slots` never finds
it, and nothing compares two aggregates.

`atomic-commit` (to be merged before this change) gives the session a transaction: changes are
collected (`add_graph`, `replace_graph`, `remove`), and on exit one update request is sent whose
first operation, the **guard operation**, is an `INSERT … WHERE` holding every guard (each version
token, each "graph absent") and writes a marker every later operation requires. A refused
transaction raises `Conflict` whose `iris` names the roots whose guard failed, found by one read
after the refused update (its DEC-3). The transaction keeps a list of guard patterns and a list of
operations, open to toolkit extensions (its DEC-6). `Session.add_graph`, `replace_graph`, `remove`
and `UnitOfWork.commit()` all go through it, so the generic router and the unit of work share one
write path.

The session is model-agnostic: it takes triples. Sessions are opened by `Tenancy._session`
(`services/tenancy.py`, which holds the `Mapper` and so the `SchemaView`), by
`testkit/fakes.fake_session`, and by consumers through `open_session`.

## Goals / Non-Goals

**Goals:** the requirements of this change: "Unique keys hold across the aggregates of a tenant"
and "Existing key duplicates can be reported" (`specs/rp-aggregate-store/spec.md`), "A unique key
across aggregates is declared with its scope" (`specs/rp-generation/spec.md`), "A key clash is a
problem of its own type" (`specs/rp-service-api/spec.md`).

**Non-goals:** the No-gos of the EPIC; any change to the in-aggregate keys' validators and shapes;
any change to the transaction's own guards, marker or batch mode beyond the hooks named here; a
key index graph; normalising values.

## Decisions

Each is the leader's choice (2026-11-12) unless marked as the developer's; the developer may
overrule any of them.

- **PD-1** (DEC-1, developer 2026-11-06): the declaration is LinkML's own `unique_keys` on an
  aggregate root (or an ancestor of roots), annotated `rp_unique_scope: tenant`. New in
  `model/rp_core.yaml`: the `RpAnnotation` value `rp_unique_scope` (meaning
  `rp:AnnotationUniqueScope`) and the enum `UniqueScope` with the one value `tenant`
  (`rp:UniqueScopeTenant`). The annotation, not the position, tells the two kinds of key apart:
  `_keys_of` (hence validators, shapes, conformance) takes only keys **without** it; the new
  `aggregate_keys` takes only keys **with** it.
- **PD-2** (DEC-1): the hard check refuses, as `HardRule.UNIQUE_KEY` problems naming class, key
  and slot: a scope other than `tenant` (through `ALLOWED_ANNOTATIONS`, with `_annotated_elements`
  now yielding each class's unique keys); a scoped key on a class that is neither a
  tenant-database aggregate root nor an ancestor of one (it would enforce nothing); a key slot that
  is not an induced slot of every such root, or that is multivalued, the identifier (written as the
  subject, never as a value), bookkeeping, or holds an owned part; `consider_nulls_inequal: false`
  (it contradicts DEC-5); an unscoped `unique_keys` declared on a tenant-database aggregate root
  class itself (it would silently do nothing, as today). An unscoped key a root only inherits from
  an ancestor (which may also type owned parts, where it is an in-aggregate key) is not refused
  (gate 2). The tenant root and system-database roots are not
  tenant-database aggregate roots, so a scoped key on them is refused: one tenant root per
  database has nothing to clash with, and the system database is not a tenant's.
- **PD-3** (DEC-1, PD-24): the runtime reads the keys from the `SchemaView`, as `Mapper` and
  `Listings` do; no artefact restates them. `schema_structure.aggregate_keys(view) ->
  list[AggregateKey]`: one entry per concrete tenant-database aggregate root and per scoped key it
  has, itself or inherited (nearest declaration of a key name wins, as `_keys_of`).
  `AggregateKey` is a new generated class of `rp_core.yaml`: `name` (string), `root_class` (uri,
  the root's expanded `class_uri`), `predicates` (uri, multivalued, in the key's slot order).
- **PD-4** (DEC-4, developer 2026-11-06): scope is per tenant and per type. "Type" is the root's
  own class IRI: the guard matches `?root a <class_uri>`, and the mapper and the router write only
  the root's own class (`Mapper._write`; `Documents`, the root type check). A subclass that
  inherits a key is its own scope: a `Magazine` never clashes with a `Publication`.
- **PD-5** (DEC-5, developer 2026-11-06): a **claim** is `(key, root, values)` for a change whose
  triples hold, about the root IRI, `rdf:type <root_class>` and exactly one object per key
  predicate. Values are compared as RDF terms (exact; `"Dune"@en` ≠ `"Dune"`), after one
  normalisation: an `xsd:string` literal becomes the plain literal of the same text, in claims
  and in guards, because Fuseki treats the two as one term and rdflib does not (gate 2). A predicate with
  no value: no claim. With two or more values: `InvalidBody` before sending (the hard check made
  the slot single-valued, and the router's shapes refuse it earlier; this guards a raw session
  call). Key claims are a private `NamedTuple` (`KeyClaim`; not atomic-commit's `_claim`, which
  refuses a root given twice) of rdflib terms in `services/unique_keys.py`: local,
  encapsulated data that never leaves the transaction; the terms cannot be a generated model's
  fields without a round trip through strings.
- **PD-6** (DEC-2): the transaction computes the claims when `add_graph` or `replace_graph` is
  called, and on exit, before sending: (a) two claims of one key with equal values → `KeyConflict`
  naming both roots, nothing sent; (b) for each claim, one `FILTER NOT EXISTS` pattern
  (`KEY_HELD`, below) joins the transaction's guards in `Transaction.commit` (PD-15), excluding the roots this transaction
  replaces or removes (their stored state is going away; their new state is a claim of its own,
  checked by (a)). Removes claim nothing.
- **PD-7** (DEC-2): the key pattern finds holders through the registry: a graph registered
  `rp:kind rp:Aggregate ; rp:ownedBy ?root`, holding `?root a <class> ; <p> <v>`. A loaded graph
  or the meta graph never counts, so loaded RDF that happens to hold the value cannot clash. The
  value pattern is written first: with its object bound, Fuseki finds it through a quad index
  instead of walking every registered graph.
- **PD-8** (DEC-5, developer 2026-11-06: 409 with its own type): `KeyConflict(Conflict)` in
  `domain/exceptions.py`, with `iris` (the transaction's roots whose claim clashed, sorted) and
  `keys` (the key names, sorted). Not the holders' IRIs: the caller may not be allowed to see them
  (a domain service can `find` them). A subclass, so code that catches `Conflict` still catches it.
  In batch mode atomic-commit's PD-9 re-raises a batch's exception as is, so a `KeyConflict`
  stays one, with its `iris` and `keys` (TC-27, task 1.2).
  New `ProblemSlug.key_conflict` in `model/service/rp_service.yaml`, title "Key conflict", 409;
  row `(errors.KeyConflict, KEY_CONFLICT)` in `ERROR_KINDS`. No detail, as for every refusal.
- **PD-9** (DEC-2, atomic-commit DEC-3 and its PD-4): diagnosis after a failed `ASK`, in order,
  inside `Transaction._diagnose`: (1) atomic-commit's read; if the commit applied, success as
  there; (2) if it names version culprits, `Conflict(iris)` (stale data must be re-read before a
  key clash means anything); (3) only when it names no root (`reasons` is empty, PD-15), and if there are key claims, one
  `SELECT` (`diagnosis`, a `UNION` of `KEY_HELD` per claim, each binding its index) gives the
  claims now held → `KeyConflict`; (4) otherwise atomic-commit's `Conflict(iris=())`, "lost a
  race". The read races with other writers: a diagnosis, not a
  guarantee; that nothing was written is the guarantee.
- **PD-10**: wiring. `Session` and `open_session` take `keys: Sequence[AggregateKey] = ()`.
  `Tenancy.__init__` computes `aggregate_keys(mapper.view)` once and passes it in `_session`, so
  every toolkit session (router, `tenant_session`, the unit of work on it) enforces the keys with
  no change to `ServiceKit`. `fake_session` takes `keys=()` and passes it on. A consumer calling
  `open_session` itself passes `keys=` or enforces none (documented; RISK-3).
- **PD-11** (DEC-6, re-shaped: Q-7): `Session.key_duplicates() -> list[KeyDuplicate]`, one
  `SELECT … GROUP BY … HAVING (COUNT(DISTINCT ?key_root) > 1)` per key, read-only, over the same
  registry join as PD-7. `KeyDuplicate` is a new generated class of `rp_core.yaml`: `key`
  (string), `root_class` (uri), `values` (string, multivalued, the lexical forms in key order),
  `roots` (uri, multivalued, sorted). An operator runs it per tenant, after declaring a key and
  before deploying it. Generation cannot do it (it reads schema files and never connects to a
  store); a start-up check was rejected (it scans every tenant on each start, and could only warn
  or stop the service over data).
- **PD-12** (DEC-3): variable-arity patterns go through two new helpers of `domain/sparql.py`:
  `value_patterns(subject, predicates) -> SparqlTerm` (`?subject <p0> ?v0 . ?subject <p1> ?v1 .`)
  and `value_variables(n) -> SparqlTerm` (`?v0 ?v1`), validating the variable name like
  `match_patterns`. Constant patterns use the existing `match_patterns`.
- **PD-13** (test data): the toy library's `Book` declares `isbn_key` over `isbn`. `isbn` appears
  in `test_mapper_unit_of_work.py`, `test_listing.py`, `test_listing_routes.py` and
  `test_roundtrip.py`, none of which stores two books with one ISBN, and an absent ISBN claims
  nothing, so existing tests are unaffected (gate 2 corrected the evidence). The generated
  artefacts the key changes (models, shapes, `rp-manifest.json`) are regenerated in the same task.
- **PD-14** (gate 2, 2026-11-12): an independent gate scored 8/10; its five findings (the order of
  `iris`, now sorted in atomic-commit PD-4 too; `KeyConflict` through batch mode; inherited
  unscoped keys; `xsd:string` normalisation; PD-13's evidence) are folded into PD-2, PD-5, PD-8,
  PD-13 and the tasks.
- **PD-15** (leader, 2026-11-14, before task 1.1; RISK-4 resolved): the PLAN checked against
  atomic-commit as built (its proposal's "As built (2026-11-13)" table) and `develop` at 38f4a41.
  - **Names.** The guard list is private, `Transaction._guards` (its PD-18a), as are
    `_operations`, `_roots` and `_read_at`. There is no `_send`: `Transaction.commit` builds the
    request with `request_text(registry, marker, guards, operations)` and confirms it.
    `_diagnose` exists; its "no culprit" branch is `reasons` being empty. The key code is added
    from inside `services` (`services/unique_keys.py` and `Transaction` itself), which is what
    PD-18a allows; nothing of the transaction becomes public.
  - **Where the guards join.** `commit` passes `[*self._guards, *key_guards]` to `request_text`;
    `_guards` itself is not changed, so the key guards are built once, when every change is
    known. The excluded roots are those with a read version: `self._roots[g]` for each `g` with
    `self._read_at[g] is not None` (replaces and removes).
  - **The in-transaction clash (PD-6a) is exact**: it compares the transaction's own claims and
    sends nothing.
  - **A `KeyConflict` from the store is a diagnosis, as `Conflict.iris` is** (atomic-commit
    PD-4: the read after the refusal can miss a root or name one too many). What is
    guaranteed: of two concurrent writers of one key value at most one commits, and a refused
    commit wrote nothing. What is best effort: the exception's type and its `iris`. Known cases,
    none changed by this PLAN:
    (a) the holder is removed before the read → `Conflict(iris=())` (TC-25); a retry passes;
    (b) another writer changes a root of the transaction between the refusal and the read → the
    version read names it and the clash is reported as a plain `Conflict`; after the re-read the
    retry raises the `KeyConflict`;
    (c) the version read misses its culprit (an add over a graph removed since, or a graph with
    no version triple) and the claimed value is held → `KeyConflict`, true of the store's state
    though not the only cause;
    (d) `iris` lists every claim held at the read, so it can name a root whose holder arrived
    after the refusal, or miss one whose holder left;
    (e) atomic-commit's false conflict (the commit applied and every graph it wrote was
    overwritten or removed before the `ASK`) can surface as a `KeyConflict` if the removed
    root's value was taken meanwhile. A re-read shows the true state.
    So `KeyConflict` means "at the read, another aggregate of the type held a value this commit
    claims", not "this is why the commit was refused". The spec delta says "as a diagnosis".
  - **The message** follows atomic-commit PD-20a: roots and key names in words, no graph IRI,
    no version token, no key value and no holder (PD-8).
  - **Batch mode** is `UnitOfWork.commit(batches=True)` (`services/mapper.py`): a batch's
    exception keeps its type and fields and gets "`n` of `m` batches committed before it"
    (TC-27 expects "1 of 2"). `UnitOfWork.discard` (38f4a41) acts before the transaction is
    opened, so a discarded root claims nothing.
- **PD-16** (leader, 2026-11-14, reading task 1.1's diff; changes PD-3 and PD-11): the slots of
  `AggregateKey` and `KeyDuplicate` are named for what they hold: `key_name` (one slot, used by
  both classes, instead of `name` and `key`), `root_class`, `key_predicates`, `key_values`,
  `key_roots`. They are global slots of `rp_core.yaml`, which every consumer schema imports; a
  slot called `name`, `key` or `values` there would meet a consumer's own slot of that name.
  TC-01 and TC-40 read with these field names.

## Algorithm / approach

`services/unique_keys.py` (new; imports only `domain`):

```python
class KeyClaim(NamedTuple):            # PD-5: local to the transaction
    key: AggregateKey
    root: URIRef
    values: tuple[URIRef | Literal, ...]

# One claimed value is held by an aggregate other than the excluded roots (PD-7); the value first.
KEY_HELD = """
  GRAPH ?key_graph { $values }
  GRAPH $registry { ?key_graph $p_kind $aggregate ; $p_owned_by ?key_root }
  FILTER (?key_root NOT IN ($excluded))
"""

def claims_of(keys, iri, triples) -> list[KeyClaim]: ... # PD-5, raises InvalidBody on 2+ values (named so by D-5 F-6)
def same_value(claims) -> list[KeyClaim]: ...          # PD-6a: the claims another claim repeats
def guard(claim, registry, excluded) -> str:           # "FILTER NOT EXISTS { KEY_HELD }"
def diagnosis(claims, registry, excluded) -> str:      # SELECT DISTINCT ?claim { {KEY_HELD BIND(0 AS ?claim)} UNION … }
def duplicates_query(key, registry) -> str:            # PD-11
```

`$values` is `match_patterns("key_root", [(RDF.type, class), (p0, v0), …])` with the value pairs
first and the type last. `?key_graph` and `?key_root` are used only inside these patterns; inside
`FILTER NOT EXISTS` they bind nothing outside, so several key guards share the names.

In `Transaction` (atomic-commit PD-5, PD-6, in `services/session.py`):

```python
# add_graph / replace_graph, after the existing pre-checks:
self._key_claims += claims(self._session._keys, iri, triples)
# commit, before request_text(...) is built (PD-15):
if clash := same_value(self._key_claims):
    raise KeyConflict(..., iris=roots_of(clash), keys=names_of(clash))   # nothing sent
excluded = self._replaced_or_removed_roots()   # the roots with a read version
guards = [*self._guards, *(guard(c, registry, excluded) for c in self._key_claims)]
# _diagnose, when the version read names no root (`reasons` empty; PD-9, PD-15):
#   if self._key_claims and (held := rows of diagnosis(self._key_claims, registry, excluded)):
#       raise KeyConflict(..., iris=roots_of(held), keys=names_of(held))
#   else: atomic-commit's Conflict(iris=())
```

`iris` and `keys` are tuples, sorted, as `Conflict.iris` (atomic-commit PD-7).

Worked example (toy library, tenant `T`, `isbn_key` over `bibo:isbn`, books `A`, `B`, `C`):

| Step | Claims | Excluded | Guard result | Outcome |
|---|---|---|---|---|
| add `A` isbn "1" | (A, "1") | — | no holder | stored |
| add `B` isbn "1" | (B, "1") | — | `A` holds "1" | refused; diagnosis: versions fine, claim 0 held → `KeyConflict(iris=[B], keys=[isbn_key])` |
| replace `A`, isbn "1" kept | (A, "1") | A | holder is `A`, excluded | stored |
| remove `A`; add `B` isbn "1", one commit | (B, "1") | A | holder `A` excluded | stored; "1" now held by `B` |
| add `C` isbn "2" and `D` isbn "2", one commit | (C,"2"), (D,"2") | — | not sent | `KeyConflict(iris=[C, D])` before any request |
| replace `B` (stale version) with isbn "2" held by `C` | (B, "2") | B | both guards fail | version diagnosis names `B` → `Conflict(iris=[B])` |
| add `E` without isbn | none | — | no key guard | stored |
| same "1" in tenant `U` | (X, "1") | — | `U`'s registry and database | stored |

Guard text for the second step (one pattern of the guard operation's `WHERE`):

```sparql
FILTER NOT EXISTS {
  GRAPH ?key_graph { ?key_root <http://purl.org/ontology/bibo/isbn> "1" .
                     ?key_root <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://purl.org/ontology/bibo/Book> . }
  GRAPH <…/libraries/t1/registry> { ?key_graph rp:kind rp:Aggregate ; rp:ownedBy ?key_root }
  FILTER (?key_root NOT IN ())
}
```

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Check a key with `find` or an `ASK` before the update | A guard pattern inside the guard operation (PD-6) | A read before the write is the race the EPIC removes (`find`'s docstring says so) |
| Match holders with `GRAPH ?g { ?r <p> <v> }` alone | Join the registry: `rp:kind rp:Aggregate ; rp:ownedBy ?r` (PD-7) | A loaded graph holding the value would clash, and a part with the same predicate would be taken for a root |
| Exclude only the root being written | Exclude every root the transaction replaces or removes (PD-6) | "Remove A, add B with A's key" in one commit would fail against A's old state |
| Treat an absent key value as a value | No claim when any key predicate is absent (PD-5) | Only one aggregate without the key could exist (DEC-5) |
| Match `?r a ?type` with any subclass, or by `rdfs:subClassOf` | Match the root's own class IRI (PD-4) | Scope is per type; subclasses are their own scope |
| Put the type pattern first in `KEY_HELD` | The value patterns first (PD-7) | With the type first, the store walks every book in the tenant per commit |
| Report a key clash as the plain `Conflict` | `KeyConflict` with its own problem type (PD-8) | A client would re-read and retry a clash that can never pass |
| Put the holder's IRI in `KeyConflict` or the problem | The transaction's own roots and the key names (PD-8) | The caller may not see the holder; a 409 carries no detail |
| Let `_keys_of` see scoped keys | Filter on the annotation (PD-1) | A scoped key on an ancestor of an owned part would also become an in-aggregate validator |
| Paste a value or IRI into a pattern with an f-string | `match_patterns`, `value_patterns`, `term` (PD-12, DEC-3) | Injection; DEC-3 forbids it |
| Check existing duplicates in generation or at start-up | `Session.key_duplicates()`, run by an operator (PD-11) | Generation has no store; start-up would scan every tenant on each start |

## Error matrix

| Input | Result |
|---|---|
| Add or replace whose claim is held by another aggregate of the type in the tenant | `KeyConflict(iris=[root], keys=[name])`, nothing written; router: 409, type `…/problems/key-conflict` |
| Two changes of one transaction with equal claims | `KeyConflict` naming both, before any request |
| Replace keeping its own key | stored (own root excluded) |
| Replace swapping keys of `A` and `B` in one transaction | stored (both excluded; claims differ) |
| Replace that is stale and also clashes | `Conflict(iris=[root])` (version first, PD-9) |
| Add over an existing root that holds the same key | `Conflict` (the add's absent guard; version diagnosis first) |
| Key predicate absent (any slot of a composite key) | no claim; never conflicts |
| Key predicate with two values in a raw session call | `InvalidBody`, nothing sent |
| A loaded graph or a part holds `<p> <v>` | not a holder (registry join, type match) |
| Same value on a subclass root, or in another tenant | stored |
| Tenant root, system-database root | never keyed (PD-2) |
| Key declared over existing duplicates; replace of one of them keeping the key | `KeyConflict` until one key changes; a remove or a key change passes. `key_duplicates()` lists them first |
| Guard refused, then the holder removed before the diagnosis read | `Conflict(iris=())` (PD-9); a retry passes |
| Batch-mode commit (atomic-commit DEC-4), equal keys in two batches | the later batch is refused against the stored earlier one; earlier batches stay (batch mode is not atomic overall) |
| Session opened without `keys` | no key enforced (PD-10) |
| Invalid declarations (PD-2) | `rp-generate` fails naming class, key, slot; no output changes |
| The store fails during the request | the store's error, unchanged; one request, nothing written |

## Risks / Trade-offs

- **RISK-1** — the guard is slow on large tenants if Fuseki evaluates the registry before the value
  (low; medium: every keyed commit). Mitigation: value pattern first (PD-7); IT-06 measures a
  keyed add against 1,000 stored books and fails above 0.5 s per commit.
  **Measured 2026-11-14 (IT-06, local Fuseki container, one run):** mean keyed add 0.049 s, mean
  add without an ISBN 0.047 s (20 adds each, tenant of 1,000 books): the guard costs about 2 ms
  per add at this size. On the fake store (rdflib) a commit of 300 keyed roots takes about 18 s,
  since rdflib evaluates each guard without an index; that is a test-time cost only.
- **RISK-2** — a consumer's schema already has an unscoped `unique_keys` on a root; generation
  now fails (low; low). Accepted: today such a key silently does nothing; the message says to add
  `rp_unique_scope: tenant` or remove it.
- **RISK-3** — a consumer opens `open_session` itself without `keys` and enforces nothing (medium;
  medium). Mitigation: the how-to and the `open_session` docstring say so; `tenant_session` passes
  them.
- **RISK-4** — `atomic-commit`'s merged code differs from its PLAN's `Transaction.guards`,
  `_send` and `_diagnose` (its PD-4 to PD-6), on which this PLAN builds (medium; low).
  **Resolved 2026-11-14 (PD-15):** the names differ (`_guards`, `commit`), the approach holds.
- **RISK-5** — numeric values written with a non-canonical lexical form compare equal on Fuseki
  (TDB2 stores numbers by value) and not on the fake, or in the in-transaction check (low; low).
  The mapper and the router write canonical forms. Accepted; noted in the how-to.
- **RISK-6** — declaring a key over existing duplicates blocks edits of those aggregates (medium
  for a consumer adding a key to live data; medium). Mitigation: `key_duplicates()` and the
  how-to's order: declare, report on every tenant, fix, deploy.
- **RISK-7** (D-5 F-8) — a 409 `key-conflict` tells anyone who may write the type that the value
  exists in the tenant, even when the aggregate holding it is hidden from them (low; medium for
  confidential values). Accepted: every tenant-wide key has it; PD-8 keeps the holder and the
  value out of the answer. The how-to says not to make a slot of confidential values a key.
- **Assumption** — `atomic-commit` lets a toolkit extension append patterns to the guard
  operation's `WHERE` and run its own read after the version diagnosis (its DEC-6, DEC-3).
  If not, this PLAN returns to the gate.

## Open Questions

None. The decisions for the developer to review are PD-2 (unscoped root keys fail generation),
PD-8 (no holder IRIs in the conflict), PD-9 (version conflict reported before a key clash) and
PD-11 (operator report instead of generation).

## Delivery decisions

- **D-1** (leader, 2026-11-14, before task 1.2): GitNexus rates `open_session` CRITICAL (2 direct
  callers, 27 flows: every router and tenancy flow opens a session) and `Transaction` MEDIUM
  (10 direct). The rule sends a HIGH or CRITICAL risk to the developer. The lead goes on and
  reports it instead of stopping, because the developer reviewed this very change (PD-10: an
  optional `keys=()` on `Session` and `open_session`) and asked for an independent run; the
  rating counts the flows through the function, and the change keeps every existing call valid:
  with no key declared the request text and the diagnosis are as before. The guard for it is
  the existing session, mapper, tenancy and router suites, which must stay green unchanged, and
  the adversarial tester right after task 1.2.
- **D-2** (leader, 2026-11-14, reading task 1.2's diff; changes PD-5; the developer may overrule):
  `KeyClaim` is a plain private class with `__slots__`, not a `NamedTuple`. The model guard
  (`testkit/guards.py`, PD-28) refuses a hand-written `NamedTuple` in `services`, and PD-5 asked
  for one; the guard is not changed and gets no allow-list entry. The class holds rdflib terms
  for the length of one transaction and never leaves `services/session.py` and
  `services/unique_keys.py`: local, encapsulated logic, not a model. A generated model was
  rejected for the reason PD-5 gives (its fields would be strings, read back into terms).
- **D-3** (leader, 2026-11-14, reading task 1.2's diff):
  (a) `value_patterns` and `value_variables` (PD-12) are not added in stage 1: nothing there
  needs them (`match_patterns` covers the claimed values). Task 2.1 adds them if the report does.
  (b) The diagnosis joins its branches with a new `union` helper of `domain/sparql.py`, beside
  `join`, so no SPARQL text is assembled outside that module (DEC-3).
  (c) A blank-node object of a key predicate is no value and claims nothing: in a pattern it
  would act as a variable and match any holder.
- **D-4** (leader, 2026-11-14; adversarial tester, accepted): `same_value` (PD-6a) counts a
  clash only between claims of **different roots**. With one `AggregateKey` given twice in
  `keys` (the public `open_session` accepts it), one root's two equal claims were taken for two
  roots and a single add raised `KeyConflict`. The test is
  `test_a_key_given_twice_does_not_clash_a_root_with_itself`.
- **D-5** (leader, 2026-11-14; stage 1 review, lenses L1, L2, L3, L4+L5; L3 had no finding).
  Accepted, fixed in one pass before the merge:
  - **F-1** (L2 W1): a value stored as `"1"^^xsd:string` did not block a plain `"1"` claim on
    the fake store, though Fuseki holds the two as one term (PD-5 normalised only the claim).
    The fake store reads an `xsd:string` literal as the plain literal when data enters it, so a
    consumer's unit tests see what Fuseki does; the reverse of TC-26 is tested on the fake, and
    both directions once on Fuseki, which also checks PD-5's premise. If the fake cannot do this
    with a small change, the fixer stops and the limit is recorded instead.
  - **F-2** (L2 W2): TC-03 also asserts that the toy has no keyed slot, validator or shape for
    `isbn_key` and that `Grant`'s key is still a keyed slot.
  - **F-3** (L2 W3): TC-08a also asserts the inherited key stays in-aggregate on `Chapter` and
    gives `Book` no key across aggregates.
  - **F-4** (L2 S1, S2): no `print` in a test; the hard-check tests assert the quoted key and
    slot names, not a substring that is always there.
  - **F-5** (L4+L5 W1): one rule for "lives in the system database": the annotation is
    inherited (`in_system_database`), and `served_roots` uses it too.
  - **F-6** (L4+L5 W2, W4, S5): `claims` becomes `claims_of`; the reading of the diagnosis rows
    moves next to the query (`held` in `unique_keys.py`); the excluded roots are computed once.
  - **F-7** (L4+L5 W3, S8, S10, S12): `UniqueScope.TENANT.value` in the hard-check message;
    `join` and `union` share one private helper; the reasons of `_key_problems` are one list;
    `class_kinds` computes a bool.
  - **F-8** (L1): a 409 on a taken value tells anyone who may write the type that the value
    exists in the tenant, even when the holder is hidden from them. No tenant-wide key can
    avoid it; PD-8 keeps the holder and the value out of the answer. Recorded as **RISK-7**
    (accepted): a slot holding confidential values should not be a scoped key; the how-to says
    so (task 2.3).
  Rejected:
  - L4+L5 S6 (a helper for two repeated lines in `add_graph` and `replace_graph`) and S7 (one
    shared `_rows` for six query sites, five of them not of this change): refactors of the
    transaction code another session changes in parallel; not this change's job.
  - L4+L5 S9 (drop `str(iri)`): callers do pass `URIRef`s; the conversion is the point.
  - L4+L5 S11 (group problem kinds by status for the `WWW-Authenticate` header): no effect
    today, one 401 kind exists.
  - L2 S4 (list the key conflict only on routes of keyed types): the spec asks that the
    document list the type; a route option per schema key is more machinery than it is worth.
  - L2 S3: TC-33 is read as "the 409 answer names the key conflict"; the document lists no
    problem slug for any kind.
- **D-6** (leader, 2026-11-14; the stage 1 checker, accepted; changes the mechanism of PD-2): a
  scope other than `tenant` is a `HardRule.UNIQUE_KEY` problem naming the class and the key,
  raised with the other key checks (`_scoped_key_reasons`), not an annotation problem naming
  only the key: the spec says "naming the class and the key", and a `UniqueKey` does not know
  its class. `_annotated_elements` yields schema elements only, as before this change.
- **D-7** (leader, 2026-11-14, before the stage 2 challenge): stage 2 uses the small review set
  of a MEDIUM appetite: two reviewers (L1+L2, and L3+L4+L5), then the checker. The stage adds
  374 lines against `develop` (limit 600), and its risk is low: a read-only report, two SPARQL
  helpers, tests and docs; nothing in the write path changes. A cold reader reads the how-to
  sections, since a how-to page changed.
- **D-8** (leader, 2026-11-14; the cold reader of the how-to, accepted): the two how-to sections
  also say: what to do after a `KeyConflict` (do not retry; change the value or tell the user)
  and that a clash can also arrive as a plain `Conflict`; that the scope is per type, at the
  declaration; that numbers compare by exact term only when canonical; how to run the report
  before the key is enforced (from a script with the new code, the service not yet deployed) and
  to run it again just before deploying; and that every root but one of a duplicate must change.
  Not taken: explaining terms the page defines in its earlier steps (bookkeeping, owned part,
  shape, `kit`, `work`), which the reader was not given.
- **D-9** (leader, 2026-11-14; stage 2 review, L1+L2 and L3+L4+L5; no critical finding).
  Correction to D-7: the stage does touch one helper of the commit guard (`_held` is split into
  `_held` and `_held_around` so the report shares its terms); the text `guard` and `diagnosis`
  build is the same, and their tests cover it. Accepted, fixed in one pass:
  - **G-1**: the report is sorted by key name, values, then roots, so two entries with equal
    lexical forms have a fixed order. `key_values` stay lexical forms (PD-11); the how-to says
    that terms of one text but another datatype or language are separate entries. One test.
  - **G-2**: the scope test of the report stores a root of another class with the same value,
    and its loaded graph holds the value about the root itself where the session allows it.
  - **G-3**: IT-05 asserts the store is unchanged, as TC-40 does.
  - **G-4**: `key_duplicates` is a plain loop; `value_variables` says why it calls `count`.
  - **G-5**: the `key_duplicates` docstring says it checks no access and what it raises; the
    how-to says "one per set of key values" and that a stored root with two values for a key
    slot appears once per value and must be brought to one; one test pins that.
  - **G-6**: `value_patterns` has a test for a raw string predicate.
  Rejected:
  - one `_variable` helper for the three copies of the variable-name check in
    `domain/sparql.py`: two of them are not this change's lines;
  - refusing an `AggregateKey` with no predicates: `aggregate_keys` cannot produce one (LinkML
    requires `unique_key_slots`), and the guard already ignores it;
  - selecting one row per root instead of `GROUP_CONCAT`: no need until a duplicate carries more
    than IRIs;
  - removing the `print` of IT-06: the task row asks for the two means to be printed.
