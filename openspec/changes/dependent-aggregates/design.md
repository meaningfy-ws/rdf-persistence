<!-- PLAN (design half) of dependent-aggregates. PLAN = this file + tasks.md. -->

# Design: dependent-aggregates

> Derives from: EPIC `dependent-aggregates` (`proposal.md`, #437 A.5), DEC-1 to DEC-7.
> Builds on `aggregate-composition` (DEC-7 «own graph», DEC-8 pointers over roots), the
> reference-collection cascade (`ReferenceCollections.delete_cascade` in
> `rdf_persistence/collaboration/services/reference_collections.py`) and the dependent records of
> #226 (`Session(dependents=…)`). Owner questions: `inputs/qa.md`. Every `PD-n`, `D-n` and
> `RISK-n` has an anchor (`design.md#pd-n`, `#d-n`, `#risk-n`) that `tasks.md` links to.

## Context

What the code already gives (read 2026-11-28):

- `Transaction` (`rdf_persistence/persistence/services/session.py`) collects every change as a
  **guard** and **marked operations** and sends one update request: `START` inserts a commit marker
  only if every guard holds, so the guards and the writes are one atomic request. Key guards
  (`rdf_persistence/persistence/services/unique_keys.py`) and referrer guards
  (`rdf_persistence/persistence/services/referrers.py`) are extra guards built the same way. `_require_present` and
  `_require_match` already guard on another aggregate's existence and class without changing it.
- `Transaction.remove` → `remove_parts` drops the graph, its loaded graphs, its registry entries and
  its #226 dependent records in the same request. Removing N aggregates in one transaction records
  one activity with one `Invalidation` each, which the relay publishes (rp-messages, rp-events).
- `referrer_guards` exclude referrers whose graphs the same transaction removes; `_still_referenced`
  turns a failed referrer guard into `InUse` (DEC-5 comes for free once the parts are removes of
  the same transaction).
- `delete_cascade` counts against `Mapper.max_roots` (`LimitSettings.max_roots`) before writing,
  raising `CommitTooLarge` with the limit only, and collects each member as `transaction.remove`.
- The session knows no schema: the kit derives `keys`, `dependents` and `removals` from the
  `SchemaView` and passes them in (`rdf_persistence/api/entrypoints/kit.py:232-246`,
  `rdf_persistence/tenancy/services/tenancy.py:211`, `rdf_persistence/testkit/fakes.py:493`).
- The access check of a delete is the route's (`rdf_persistence/api/entrypoints/router.py`), on the IRI deleted; the session checks
  none (DEC-2 needs no access code).
- The converter refuses a generated «own graph» part (`aggregate-composition` DEC-7); that code is
  not on `develop` yet (RISK-6).
- Guards are evaluated on the state **before** the request's own operations (`START … WHERE
  { guards }`), on Fuseki (one TDB2 write transaction) and on the fake (one copy, no `await`). So a
  guard never sees a change of the same request: same-transaction cases are checked before
  sending (PD-3, PD-5).
- Reading of DEC-5 (A-11): `aggregate-composition` DEC-8 refuses pointers to *owned* classes, not to
  dependent roots, so a dependent root is a legal pointer target (the toy's `Audit.cites_finding`).
  A non-refusing part referred to from outside leaves a dangling reference after the cascade, as any
  deleted root does; a refusing one refuses the delete (PD-8). Recorded in `inputs/qa.md`.

## Goals / Non-Goals

**Goals**
- G-1: a dependent part is written (add or replace) only while its whole exists and is of the
  annotated class, checked in the write's own request; else `NotFound`, nothing written (DEC-3).
- G-2: a part's pointer never changes after creation (`Conflict`) (DEC-3).
- G-3: removing a whole, by any path (`Session.remove`, a `Transaction`, a unit of work, the generic
  delete, a collection cascade), removes its dependent parts transitively with their loaded graphs,
  in one request, all or nothing, under `max_roots` (DEC-2, DEC-4, DEC-5, DEC-6).
- G-4: `rp-generate` refuses a bad pointer slot and a cycle of dependence (DEC-7).
- G-5: the converter emits a generated «own graph» part as a dependent root (DEC-1).

**Non-Goals**: the EPIC's no-gos; changes to #226 dependent records (comments) or to
`delete_cascade`.

## Decisions

- <a id="pd-1"></a>**PD-1** (DEC-1): metamodel. `RpAnnotation` (`rdf_persistence/model/rp_core.yaml`) gains
  `rp_dependent_on`: class annotation on an aggregate root naming its pointer slot. Read like
  `rp_on_referenced_delete`: from the first class of the `is_a` chain that carries it (mixins do
  not count), so a subclass of a dependent root is dependent too. The annotation may sit on an
  abstract base whose concrete subclasses are served roots; a subclass may not re-annotate with
  another slot (PD-12, A-10). `make generate` (lead only)
  regenerates `rp_core.py`, the shapes, the context and the TS enum. *Rejected:* a slot-level
  annotation on the pointer (a class may have several root-valued slots; the class is what is
  dependent).
- <a id="pd-2"></a>**PD-2** (P-0007): the runtime reads a generated concept, not tuples or dicts. A new class
  `DependenceLink` in `model/technical/persistence/rp_persistence_services.yaml`: `part_classes`
  (IRIs of the dependent class and its concrete subclasses), `pointer` (the slot's predicate IRI),
  `whole_classes` (IRIs of the range class and its concrete subclasses). `schema_structure.dependence_links(view)`
  builds them; `make generate` (lead only). The name avoids `dependents` (#226 records). *Rejected:*
  reusing the `Dependents` pairs (no events, no versions, not transitive, no loaded graphs).
- <a id="pd-3"></a>**PD-3** (DEC-3, P-0008): the whole check is one more guard of the part's request, built like
  `_require_match`: `GRAPH <wg> { <wg> rp:version ?wv$n . <w> a ?wt$n FILTER (?wt$n IN (whole classes)) }`.
  `Transaction.add_graph` and `replace_graph` only read the pointer from the prepared triples
  (refusing a bad one at once, below) and record `part -> whole`. Everything else runs **at
  commit**, after PD-5's steps (1) and (2) (G-2), so the order in which a transaction collects a
  whole and its part does not matter: for each recorded part whose whole is not removed, a whole
  added or replaced in the transaction is judged by its collected triples; any other whole gets a
  `Session.matches`-style ASK (the early `NotFound`) and the guard, which closes the race. A pointer that is not an aggregate IRI of the tenant is `NotFound`
  too (the whole does not exist here), not `InvalidIri`. When the whole is **added or replaced** in
  the same transaction, its class is read from the collected triples (a guard would see the
  pre-state, A-3); for an add no store guard is added (its absence guard and atomicity cover it).
  A part with no pointer value or several, or pointing at its own IRI (A-7), is `InvalidBody`
  (the API's SHACL refuses most of it first; the session refuses it for in-process callers). The
  transaction keeps `_wholes: whole graph -> (part, whole)` for the diagnosis (PD-11).
- <a id="pd-4"></a>**PD-4** (DEC-3): pointer fixity. `replace_graph` of a part reads the stored pointer
  (`root_values`, existing `READ_ROOT_VALUES`) and refuses a different value with `Conflict`
  naming the slot, before sending. The replace's version guard ensures the value read is the one
  replaced. *Rejected:* a pointer-equality guard in the request (the version guard already pins it).
- <a id="pd-5"></a>**PD-5** (DEC-2, DEC-4; A-1, A-2): the cascade is expanded **at commit**, as the **first** step of
  `_send_and_confirm`, before the key-claim check, `_refuse_links_to_removed`,
  `_refuse_dependents_of_removed`, `_excluded()` and every guard, so all of them see the cascaded
  removals. Order: (1) transitive expansion from every removed root (PD-6); (2) the same-transaction
  check over **every** removed root, explicit or cascaded: an add or replace collected in this
  transaction whose pointer names a removed root is refused with `Conflict` naming the part and the
  whole (the whole named under PD-10), nothing sent; (3) PD-3's whole checks; (4) the existing
  pre-checks and guards. In step (1), a discovered part the transaction already holds a change for
  (a remove, an add or a replace) is not collected again, so `_claim`'s `ValueError` never fires,
  but it is still discovered from; an added or replaced one then meets step (2)'s `Conflict` (G-1:
  replacing R1 and removing A1 in one transaction is a `Conflict` naming R1 and A1). Not in
  `Transaction.remove`. *Rejected:* expanding in `remove()` (a later `replace_graph` of the same
  part would hit `_claim`'s `ValueError`, and adds made after the remove would be missed).
- <a id="pd-6"></a>**PD-6** (DEC-4): discovery reads the parts level by level, one query per level for all wholes of
  that level (`VALUES ?whole`), each row the part, its type and version, starting from the pointer
  triple, `LIMIT max_roots + 1`. It starts from every removed root and keeps a visited set, so a
  root reached twice is read once and a loop stops (A-7). It stops as soon as
  `len(set(roots) ∪ found)` exceeds `max_roots` (a root the caller removes and the cascade finds
  counts once, A-7) and raises `CommitTooLarge` with the limit only (as `_require_room`). Then each
  part not yet removed is collected through a private `Transaction._remove_read(part, version,
  type)` that reuses discovery's version and type instead of `_stored` (A-15) and otherwise does
  what `remove` does (graph, loaded graphs, entries, #226 records, delete validators, D-1); a part
  gone meanwhile fails its version guard (PD-11). The session receives the limit with the links
  (`dependence=…, max_roots=…`), from the same `LimitSettings` the mapper uses (P-0009);
  `max_roots` is required whenever `dependence` is non-empty, else the constructor raises
  `ValueError` (A-8). *Rejected:* a SPARQL property path across graphs (each part is in its own
  graph; not portable); batching (DEC-4).
- <a id="pd-7"></a>**PD-7** (DEC-3, DEC-4): the delete's request carries a **no-late-part** guard per removed root
  when the session has links: no registered aggregate of a part class whose pointer names that root
  and whose graph is not removed by this request. A part written between discovery and the delete
  fails the delete with `Conflict` ("a part of W was added since its parts were read; retry"),
  naming W only. Together with PD-3 this makes both orders safe on a store that runs one update
  request at a time (RISK-1). The guarded roots are kept in `_unlated` for the diagnosis (PD-11).
  Parts written without pause can starve the delete (RISK-8, D-3).
- <a id="pd-8"></a>**PD-8** (DEC-5): no new code for `InUse`: the parts are removes of the transaction, so
  `referrer_guards` and `_still_referenced` already refuse a refusing part referred to from outside
  the cascade and ignore the part → whole pointers. The diagnosis maps a cascaded part to its whole
  (PD-10).
- <a id="pd-9"></a>**PD-9** (DEC-6): no event code. One commit, one `Remove` activity, one `Invalidation` per removed
  aggregate; the relay and SSE filter per aggregate as today. A test proves it.
- <a id="pd-10"></a>**PD-10** (RISK-3; A-6): a cascaded part the caller may not read is never named. The transaction
  keeps `_cascaded: graph -> whole` (the explicitly removed root it was reached from). `_reasons`
  words a part's conflict as "a part of W changed since the delete read it" with `iris=(W,)`.
  Every exception raised while collecting a cascaded part (`prepare_remove`'s `Conflict` and
  `RuntimeError`, a delete validator's `Refused`) and the `InUse` built by `_still_referenced` for
  a cascaded part are rewritten: message and `iris` name W and "a dependent part" unless
  `Session.may_read(part)` is true; the original is kept as `__cause__`, for logs only. The type
  is kept. `CommitTooLarge` gives the limit.
- <a id="pd-11"></a>**PD-11** (DEC-3; A-5): diagnosis. `_versions_found` also reads the graphs of `_wholes` and
  `_unlated`. `_diagnose` checks, in order: (1) a whole in `_wholes` with no version or not of a
  whole class now → `NotFound` naming that whole (a retry cannot succeed); (2) an ASK per root in
  `_unlated` for a part outside the removed graphs → `Conflict` naming the explicitly removed root
  it came from (PD-10); (3) `_reasons`; (4) `_refused_by_store`. Tests assert type and `iris`.
- <a id="pd-12"></a>**PD-12** (DEC-7): new module `rdf_persistence_generation/checks/dependence.py`, called from
  `boundary_problems`, rule `BoundaryRule.DEPENDENCE` (new value in `model/rp_generation.yaml`,
  `make generate`, lead). Problems (A-10, A-12): the annotated class is neither a served root nor an
  abstract class whose concrete subclasses are all served roots; a subclass re-annotates with
  another slot; for **each concrete part class**, the *induced* slot (after `slot_usage`) is
  missing, not `required` or multivalued; its range is not a served root nor an abstract class
  whose concrete subclasses are all served roots, or it is the tenant root or a toolkit-written
  root; a cycle of dependence (self included), found over concrete classes after expanding ranges
  to their concrete subclasses, naming its classes in order. *Rejected:* a hard-check `ALLOWED_ANNOTATIONS` entry (the value is a slot name, not an enum).
- <a id="pd-13"></a>**PD-13** (DEC-1, lifts `aggregate-composition` DEC-7): converter. An «own graph» composition whose
  part is generated makes the part a root (`AggregateRoot`, `rp_path` as for any root) with
  `rp_dependent_on: <slot>`, the slot being the association's role on the **whole's** end, emitted
  `required: true`, single-valued, ranging over the whole. No role on the whole's end, or a
  multiplicity other than `1`/`1..1`, is a problem naming the association. A role on the part's end
  is not converted (the whole lists no parts, DEC-1) and gets a report line. The refusal problem of
  `aggregate-composition` is removed with its test. Code: `rdf_persistence_generation/uml/links.py`,
  `rdf_persistence_generation/uml/classes.py`.
- <a id="pd-14"></a>**PD-14**: toy domain. A new module `tests/fixtures/library/audits.yaml` imported by
  `library.yaml`: `Audit` (root, `audits`), `AuditResult` (`rp_dependent_on: of_audit`,
  `audit-results`), `AuditFinding` (`rp_dependent_on: of_result`, `audit-findings`,
  `rp_on_referenced_delete: refuse`), and `Audit.cites_finding` (a slot over `AuditFinding`, the
  outside referrer of DEC-5). The lead runs `make generate` and refreshes the goldens it changes
  (OpenAPI, public surface, TS) in the same commit.
- <a id="pd-15"></a>**PD-15** (P-0010): the discovery runs in a span `rp.session.cascade` (`traced`), its log lines
  through `log_extra(LogContext(step="cascade", …))`; no new `LogContext` slot.
- <a id="pd-16"></a>**PD-16**: docs. `user-manual/model.adoc` (the annotation, DEC-7 rules), `user-manual/store-and-read.adoc`
  (the EPIC's "aggregate store how-to": write guard, cascade, limit, errors, D-1's validators,
  retrying a delete refused by live part writers (RISK-8), batch mode not atomic across batches),
  `howto/uml-to-linkml.adoc` («own graph» generated part); `questions.adoc` gains "How do I store a
  part apart from its whole and still delete it with the whole?". `make check-docs`.
- <a id="pd-17"></a>**PD-17**: delivery order. Stages 1–2 do not depend on `aggregate-composition`; stage 3 starts
  after its converter stage is merged into `develop`. The `rp-uml-import` delta is written ADDED
  here; once `aggregate-composition` is archived, the lead turns it into a MODIFIED of the
  requirement that holds the refusal scenario (task 3.1).
- <a id="pd-18"></a>**PD-18** (A-17): contract. The OpenAPI document lists a 404 `not-found` answer on the create and
  replace routes of a dependent class, and a 413 `payload-too-large` on the delete route of a whole
  class, as it lists `in-use` per class today. The lead refreshes the OpenAPI golden in the same
  commit (task 2.7). The listing filter on the pointer slot is tested, not assumed (task 2.7).

## Algorithm / approach

Toy: `Audit` A1 ◆«own graph» `AuditResult` R1, R2 (`of_audit`) ◆«own graph» `AuditFinding` F1
(`of_result` → R1); R1 has a loaded graph L1.

**Part write** (`POST /audit-results` with `of_audit: A1`, or `session.add_graph(R3, …)`):
1. write guards prepare the triples; exactly one `of_audit` value → A1 (else `InvalidBody`);
2. at commit, after the cascade (PD-5): A1 not added or replaced in this transaction → ASK A1 is
   an `Audit` (else `NotFound` "A1", nothing sent);
3. guard appended: A1's graph has a version and A1 `a lib:Audit`; the request is sent;
4. if A1 was deleted meanwhile, `START` inserts no marker, nothing is written, the diagnosis
   raises `NotFound` naming A1 (PD-11). Replace of R1 adds PD-4's pointer check first.

**Whole delete** (`DELETE /audits/A1`, caller holds delete on A1 only):
1. route checks access on A1; `transaction.remove(A1, v)` collected;
2. commit, first step (PD-5, PD-6): level 1 query on `VALUES ?whole {A1}` → R1@v1, R2@v2; level 2
   on `{R1, R2}` → F1@v3; level 3 → none. Count |{A1, R1, R2, F1}| = 4 ≤ `max_roots`;
   `_remove_read` of R1, R2, F1, `_cascaded` filled; then the same-transaction check (an add of F9
   → R1 in this commit is a `Conflict`), then the existing pre-checks;
3. guards: A1, R1, R2, F1 at their versions; referrer guards (F1 refusing: no referrer outside
   {A1, R1, R2, F1}); no-late-part guards for A1, R1, R2, F1 (PD-7);
4. one request drops four graphs, L1, their entries; one `Remove` activity with four invalidations.
   If A2 `cites_finding` F1: the referrer guard fails → `InUse` (F1 named only if readable).

Discovery query (one level):

```sparql
SELECT ?whole ?part ?type ?version WHERE {
  VALUES ?whole { $wholes }  VALUES (?type ?pointer) { $links }
  GRAPH ?g { ?part ?pointer ?whole ; a ?type . ?g rp:version ?version }
  GRAPH $registry { ?g rp:kind rp:Aggregate ; rp:ownedBy ?part }
} ORDER BY ?part LIMIT $max_plus_one
```

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Check the whole with a read, then write | Guard in the same request (PD-3) | A concurrent delete passes between them (DEC-3) |
| Extend `_DROP_DEPENDENTS` to parts | Collect each part as a remove (PD-6) | No version, no event, no loaded graphs, not transitive |
| Check the caller's rights on each part | Access on the whole only (DEC-2) | A part cannot exist without its whole |
| Name a cascaded part in an error | Name the whole unless readable (PD-10) | Leaks parts the caller may not read |
| Pass `(class, predicate)` tuples to the session | `DependenceLink` (PD-2) | P-0007 |
| Hand-edit `rp_core.py` or `rp_generation.py` | Change the YAML, `make generate` (lead) | LinkML is the single source |

## Error matrix

| Failure mode | Detected by | Response | Fallback |
|---|---|---|---|
| Part write, whole absent / wrong class / not an IRI of the tenant | commit-time ASK (PD-3) | `NotFound` naming the whole; 404; nothing sent | none |
| Whole deleted between that ASK and the part's request | whole guard (PD-3) | `NotFound` naming the whole (PD-11) | none |
| Part with no or two pointer values, or pointing at itself (in-process) | `add_graph` / `replace_graph` (PD-3) | `InvalidBody` | none |
| Whole added or replaced in the same transaction, before or after its part | collected triples at commit (PD-3, G-2) | accepted when of a whole class; else `NotFound`, nothing sent | none |
| Part added or replaced in the transaction under a whole it removes, explicitly or by cascade (e.g. replace R1 + remove A1) | expansion skips held parts, then the same-transaction check (PD-5, A-2, G-1) | `Conflict` naming both (whole under PD-10); nothing sent | none |
| Part replace changes the pointer | `root_values` check (PD-4) | `Conflict` naming the slot; 409 | none |
| Commit adds a referrer (A2 `cites_finding` F1, or a #226 comment on R1) to a part the cascade removes | existing pre-checks, run after expansion (PD-5, A-1) | `InUse` / `Conflict` as today; nothing sent | none |
| Cascade larger than `max_roots` (a root counted once) | count during discovery (PD-6) | `CommitTooLarge`, limit only; 413; nothing sent | caller deletes parts first or raises the limit |
| Session built with `dependence` and no `max_roots` | constructor (PD-6, A-8) | `ValueError` | none |
| Discovery revisits a root | visited set (PD-6, A-7) | read once; no loop | none |
| Part written after discovery, before the delete | no-late-part guard (PD-7) | `Conflict` naming the whole (PD-11) | retry; may repeat under live writers (RISK-8) |
| Cascaded part changed or removed meanwhile | version guard | `Conflict` naming the whole (PD-10) | retry (RISK-8) |
| Refusing part referred to from outside the cascade | referrer guard (PD-8) | `InUse`; part named only if readable (PD-10) | none |
| Delete validator refuses a part, or `prepare_remove` raises for it | `prepare_remove` (D-1) | its type; whole delete refused; part named only if readable (PD-10, A-6) | none |
| Unit of work in batch mode removing a whole | per-batch transaction | each batch cascades within its own limit; `CommitTooLarge` from that batch | the batch stays pending for a retry |
| Batch mode: a part of a whole removed in an earlier batch (A-9) | whole guard in its batch | `NotFound` in that batch | earlier batches stay (batch mode is documented non-atomic) |
| Load on a part between discovery and the delete (A-16) | owner terms evaluated in-request | a committed load is dropped with the part | a still-pending load is left to the sweep (RISK-2) |
| Bad pointer slot, bad annotation placement, re-annotation, pointer over the tenant root, dependence cycle | `dependence_problems` (PD-12) | `rp-generate` fails naming class and slot | none |
| «own graph» generated part with no whole-end role or multiplicity ≠ 1 | converter (PD-13) | problem naming the association | none |
| Orphan parts stored before the annotation | not detected | their replace answers `NotFound` | RISK-5 |

## Risks / Trade-offs

- <a id="risk-1"></a>**RISK-1** (low, high): a store that ran two update requests interleaved would let a part slip
  past a whole delete. The guards of PD-3 and PD-7 are correct only for serialised update requests,
  the same assumption the key and referrer guards make. Mitigation: integration test on Fuseki
  (task 2.8) runs part writes and the whole's delete concurrently and asserts no orphan, plus two
  deterministic interleavings (IT-D4, IT-D5, A-13); the store conformance suite gains "a guard
  reads a graph the request does not write".
- <a id="risk-2"></a>**RISK-2** (low, medium): partial cascade. None by construction: one request; loaded graphs drop
  in it. A crash before the request leaves everything. Accepted: loaded graphs of a part loaded but
  not yet committed are left to the existing pending-load sweep.
- <a id="risk-3"></a>**RISK-3** (medium, medium): access leaks. Mitigated by PD-10 (names), PD-6 (limit only, no count),
  SSE filtering per invalidation; tested in task 2.6.
- <a id="risk-4"></a>**RISK-4** (low, medium; A-15): cost on wide wholes: one query per level (`LIMIT max_roots + 1`);
  no `_stored` read per part (PD-6), but with delete rules one `get_graph` per part (D-1) and, on a
  refusal, one referrer read per refusing part: up to ~`max_roots` round trips before the request.
  Accepted; the manual says a wide whole with delete rules is slow to delete.
- <a id="risk-5"></a>**RISK-5** (medium, low): consumer data written before adopting the annotation may hold parts whose
  whole is gone; their replace answers `NotFound`. Accepted (no migration, no sweep: no-gos); the
  manual says so.
- <a id="risk-6"></a>**RISK-6** (medium, medium): `aggregate-composition`'s converter is not merged; stage 3 waits for it
  (PD-17).
- <a id="risk-7"></a>**RISK-7** (low, low): the toy schema grows; goldens change in PD-14's commit and the OpenAPI
  golden again in PD-18's (task 2.7).
- <a id="risk-8"></a>**RISK-8** (medium, medium; A-4, D-3): a whole under steady part writes may not be deletable: each
  part add between discovery and send fails PD-7, each part replace fails the cascaded version
  guard. The delete answers `Conflict` naming the whole; the consumer stops its writers first or
  retries with back-off; the manual says so (PD-16).

## Tests: moved or rewritten

None moved. One rewritten: `aggregate-composition`'s converter test that a generated «own graph»
part is refused becomes the emission test (task 3.2), still in `tests/generator/unit/`, lane
`make test-generator`. New tests: `tests/unit/persistence/` (`make test-unit`),
`tests/unit/schema/`, `tests/feature/` (`make test-feature`), `tests/generator/` (`make
test-generator`), `tests/integration/store/` (`make test-containers`).

## Spec deltas

`rp-metamodel`: ADDED "A root may depend on another root". `rp-generation`: ADDED "A dependent
class points at its whole with a required single slot". `rp-aggregate-store`: ADDED "A dependent
part is written only while its whole exists" and "Deleting a whole deletes its dependent parts".
`rp-service-api`: ADDED "A whole's delete removes its dependent parts". `rp-uml-import`: ADDED
"An «own graph» composition to a generated part converts to a dependent root" (PD-17).

## Open Questions

None open. Both below were decided by the lead (R-0007) and are listed under Delivery decisions.

## Delivery decisions

Decisions the lead took without the developer, shown for validation at the end (R-0007).

- <a id="d-1"></a>**D-1 (was OPEN-1)**, lead, 2026-11-28: a part's consumer delete validators (`prepare_remove`) run
  in the cascade; a business refusal refuses the whole delete, all or nothing; the manual says so.
  Rejected: skipping them, which would let a cascade delete what a direct delete refuses.
- <a id="d-2"></a>**D-2 (was OPEN-2)**, lead, 2026-11-28: DEC-6 reads as one activity per commit, with one
  invalidation per removed aggregate (PD-9); no new event shape.
- <a id="d-3"></a>**D-3** (A-4), lead, 2026-11-28: starvation of a whole's delete by parts written continuously is
  accepted as RISK-8: the delete answers a `Conflict` naming the whole, the caller retries, and the
  manual says so. No pattern sweep inside the update (it would bypass per-part validators,
  loaded-graph removal and events). Also rejected: guarding cascaded parts on existence instead of
  their version (the invalidation would record a version the delete never read, and D-1's
  validators judged another state).
