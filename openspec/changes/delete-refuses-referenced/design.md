<!-- PLAN (design half) of delete-refuses-referenced. PLAN = this file + tasks.md.
     Read against develop at 4e8d1fe2. Paths are from the repository root. -->

> Derives from: EPIC `delete-refuses-referenced` (proposal.md, issue #201); DEC-1 to DEC-3.
> Appetite MEDIUM since the owner's re-shape of 2026-11-20 (`inputs/qa.md`).

# Design: delete-refuses-referenced

## Context

- `Session.referrer_rows(iri)` (`rdf_persistence/persistence/services/session.py`, `READ_REFERRERS`)
  reads every registered aggregate graph holding a statement whose object is `iri` (not the
  graph's own bookkeeping, not `rdf:type`, not a `dependents` pair such as a comment's target).
  `Collaboration.referrers` names the rows with the schema (`_named`, `_slot_name`) and filters them
  by `AccessRules.may(…, READ)` (`collaboration/services/collaboration.py:98-276`).
- Every write is one update request (`Transaction`, session.py:1215): `START` inserts the commit
  marker only if every guard holds, each later operation runs only while the marker is there, and
  a failed confirmation is diagnosed (`_diagnose`, session.py:1632). Key guards are built at commit
  time from the transaction's claims and diagnosed after a refusal (`unique_keys.py`): the model
  this change copies.
- The generic `DELETE /{type}/{id}` calls `Aggregates.remove` (`api/services/aggregates.py:133`),
  which calls `Session.remove`. The unit of work (`mapper.py:490`), `remove_with_files` and
  `ReferenceCollections.delete_cascade` (`reference_collections.py:199`) all reach
  `Transaction.remove`. A guard in `Transaction` covers them all.
- A session "checks no access; a caller of `session` holds the session's full reach"
  (`collaboration.py:93-95`). `Collaboration.referrers` judges a comment referrer by its thread
  (`Discussion.judged`, `discussion.py:221`) and any other by `may` (`_readable`). Schema-aware checks reach the session through an injected protocol
  (`WriteGuard`, built in `collaboration/services/write_guards.py`, wired in `api/entrypoints/kit.py:211`).
- 409 problems carry no `detail` (`api/entrypoints/problems.py`, docstring); `Problem` and
  `ProblemSlug` are generated from `rdf_persistence/model/technical/api/rp_api_entrypoints.yaml`.
- Class annotations: `RpAnnotation` and the value enums in `rdf_persistence/model/rp_core.yaml`;
  the hard check validates values through `ALLOWED_ANNOTATIONS`
  (`rdf_persistence_generation/checks/hard.py:81`). The UML converter (`uml-to-linkml` DEC-2) maps
  every `RpAnnotation` entry whose description starts "Class annotation".
- Settings: `LimitSettings` in `rdf_persistence/model/technical/persistence/rp_persistence_settings.yaml`
  (`max_roots` is the model), reached as `ToolkitSettings.limits`.

## Goals / Non-Goals

**Goals**
- G-1: a class annotated `rp_on_referenced_delete: refuse` (or derived from one) is never removed
  while another aggregate graph refers to it at the moment the delete's request is applied, on
  every path that reaches `Transaction.remove`.
- G-2: the refusal is `InUse` in-process and `409` problem `in-use` over HTTP, naming readable
  referrers (capped) and counting the rest; nothing is deleted.
- G-3: classes without the annotation behave exactly as today (no extra query, no extra guard).

**Non-Goals** (the EPIC's no-gos, plus)
- Refusing a later write that names an IRI already deleted (RISK-1).
- Any change to `referrers`' results or to `READ_REFERRERS`' semantics.
- A delete route for `delete_cascade` (it stays in-process).

## Decisions

| ID | Decision | Rejected, and why |
|---|---|---|
| PD-1 | Metamodel: `RpAnnotation.rp_on_referenced_delete` (meaning `rp:AnnotationOnReferencedDelete`), description starting "Class annotation (see OnReferencedDelete)." so the UML converter finds it (DEC-1); enum `OnReferencedDelete` with the one value `refuse` (`rp:OnReferencedDeleteRefuse`); a row in `ALLOWED_ANNOTATIONS`. | A boolean: a later policy would need a second tag. |
| PD-2 | Inheritance follows the `is_a` chain only, as `workflow` does (`workflow_name_of`, `schema_structure.py:83-92`, `class_ancestors(…, mixins=False)`): a class refuses when it or an `is_a` ancestor carries `rp_on_referenced_delete: refuse`. A mixin's annotation is not inherited. `schema_structure.refusing_classes(view) -> frozenset[URIRef]` returns the class IRIs of every class of the view that meets this, computed once. | Exact class only: a root of a subclass would slip through. Mixins too: unlike every other class annotation of the toolkit. |
| PD-3 | The check is a store guard of the delete's own update request (DEC-2): one `FILTER NOT EXISTS` per removed root, added to `START`'s guards at commit time. Its pattern is `READ_REFERRERS`' `WHERE` (shared as one template fragment, its variables suffixed with the guard index), restricted to roots typed with a refusing class, and excluding the graphs this transaction removes. | A `referrer_rows` read before the request: races (DEC-2). |
| PD-4 | After a refused request, `_diagnose` adds one step after the key-claim step: for each removed root (sorted) that is of a refusing class, read `referrer_rows`, drop rows whose referrer is removed by this transaction; the first root with rows left raises `InUse`. Version reasons still win (`Conflict`), then `KeyConflict`, then `InUse`, then "lost a race". | Raising `InUse` from the guard alone: the request cannot say which guard failed. |
| PD-5 | An add or replace in the same transaction whose new triples have a removed refusing root as object raises `InUse` before anything is sent (exact, like a key clash within one commit). A replaced graph stays in the store guard with its stored state, so dropping the link and deleting the target in one transaction is refused (error matrix row 6). The types of a removed root are read with `session.heads([iri])` only when such an add or replace exists. | Excluding replaced graphs and judging their new triples: more code for a rare case. |
| PD-6 | `InUse(Conflict)` in `core/domain/exceptions.py`: `iris` = the refused roots found referenced, sorted; `referrers: tuple[tuple[str, str, str], ...]` = `(referrer IRI, class name, slot name)` of the first refused root, sorted, the same strings as `Referrer`; `more_count` = readable referrer aggregates left out by the cap; `hidden_count` = referrer aggregates not readable. A `Conflict` subclass, as `KeyConflict`. | Holding the generated `Referrer`: `domain` cannot import a services model. |
| PD-7 | The schema side is `ReferencedRemovals` (`collaboration/services/referenced_removals.py`), built once by the kit like `WriteGuards`, implementing a `RemovalRefusal` protocol declared in `session.py`: `refusing: frozenset[URIRef]` and `async in_use(roots, rows, readable) -> InUse` (`readable` as PD-9, `None` for full reach). `Session`, `open_session` and `Tenancy` take `removals: RemovalRefusal \| None = None` (none: no guard, G-3). | Teaching the session the schema: it knows none by design. |
| PD-8 | The naming of rows (`_classes_by_iri`, `_named`, `_slot_name`) moves from `Collaboration` to functions in `collaboration/services/referrer_naming.py`, used by both; `Collaboration.referrers` keeps its results (no-go). | A copy: two namings drift. |
| PD-9 | Who is "readable" is today's rule of `Collaboration.referrers` (DEC-3): a comment by `Discussion.judged`, any other referrer by `may(…, READ)`. It moves out of `referrers` into a public `Collaboration.readable_referrers(iri, rows) -> set[str]` (async), which `referrers` then calls. `Session.transaction(served, *, readable=None)` and `Session.remove(…, *, readable=None)` carry that callable (`Readable = Callable[[str, Sequence[ReferrerRow]], Awaitable[set[str]]]`, declared in `session.py`); `None` is the session's full reach (every referrer readable). `Aggregates.remove` takes `readable`; the route opens `kit.collaboration(checked)` and passes its `readable_referrers`; `Collaboration.delete_cascade` passes its own to `ReferenceCollections.delete_cascade(…, readable=…)`. | Filtering after the session capped the list: the cap would hide readable ones. A plain `may` callable: it would name or hide comments unlike `referrers` does. |
| PD-10 | The cap: `LimitSettings.max_named_referrers`, integer, default `20`, `minimum_value: 0` (0 names none and counts all). The readable referrer aggregates are sorted by IRI; the first `max_named_referrers` are named with every `(class, slot)` item they hold; the rest are `more_count`. | A per-call option (EPIC rabbit-hole). |
| PD-11 | HTTP: `ProblemSlug.in_use` (title "In use", 409, `rp:inUse`); class `InUseProblem` (`is_a: Problem`) with optional slots `referrers` (range `Referrer`, inlined list, imported from `../collaboration/rp_collaboration_services`), `more_count`, `hidden_count`. The problem handler answers `InUse` with an `InUseProblem`; `detail` stays empty. The extension members are the one 409 that says more, because they are filtered by readability first. The `DELETE` route of a refusing class documents 409 with `InUseProblem` (its extras optional, so a version-conflict body validates too). | A text `detail`: unparseable by clients, and it would break the 409 rule. |
| PD-12 | `delete_cascade` (EPIC rabbit-hole): the removes stay in one transaction; a member of a refusing class referenced from outside the cascade refuses the whole cascade with `InUse` (`iris` = the refused members), nothing deleted. Referrers removed by the same cascade (the collection, other members) do not count. Owner's decision (OPEN-1, `inputs/qa.md`). | Skipping the member: a cascade that silently keeps some members. |
| PD-13 | Test fixture: the toy library gains a root `Author` (`lib:Author`, `rp_path: authors`, `rp_on_referenced_delete: refuse`) and the slot `Book.written_by` (`lib:writtenBy`, range `Author`). No existing class is annotated, so no existing test changes behaviour. | Annotating `Shelf` or `Book`: every existing test that deletes a referenced one would change. |

## Algorithm / approach

The guard (PD-3), for removed root `$root` at guard index `n`, `$removed` = graphs this
transaction removes, `$refusing` = `removals.refusing`:

```sparql
FILTER NOT EXISTS {
  GRAPH $graph { $root a ?t$n } VALUES ?t$n { $refusing }
  GRAPH ?g$n { ?s$n ?p$n $root . ?r$n a ?c$n }
  GRAPH $registry { ?g$n $p_kind $aggregate ; $p_owned_by ?r$n }
  FILTER (?s$n != ?g$n && ?p$n != $rdf_type && ?g$n NOT IN ($removed))
  $not_dependent                       # _NOT_DEPENDENT over ?p$n, ?c$n
}
```

Commit (`_send_and_confirm`), in order: key clash within the commit → `KeyConflict`; PD-5 check →
`InUse`; build key guards and referrer guards; send. A session with `removals is None` or an empty
`refusing` adds nothing.

Worked examples (toy, PD-13; A1 an author, B1 a book, S1 a shelf; Ada may read B1, not B2):

| # | State | Call | Result |
|---|---|---|---|
| E1 | B1 `written_by` A1 | `DELETE /authors/a1` as Ada | 409 `in-use`, `referrers: [{B1, Book, written_by}]`, `more_count 0`, `hidden_count 0`; A1 stays |
| E2 | only B2 `written_by` A1 | same | 409, no `referrers`, `hidden_count 1` |
| E3 | no referrer | same | 204 |
| E4 | B1 `sequel_of` B0 (Book not annotated) | `DELETE /books/b0` | 204, as today |
| E5 | 25 readable books refer to A1, `max_named_referrers` 20 | `session.remove(A1, v)` | `InUse`, 20 referrers named, `more_count 5`, `hidden_count 0` |
| E6 | S1 (member class Author) names A1; B1 refers to A1 | `delete_cascade(S1, v)` | `InUse(iris=(A1,))` naming B1; S1 and A1 stay |
| E7 | S1 names A1; nothing else refers to A1 | `delete_cascade(S1, v)` | S1 and A1 deleted (S1's own link does not count) |
| E8 | S1 names A1 | `DELETE /authors/a1` | 409 naming `(S1, Shelf, had_member)` (OPEN-2, decided) |
| E9 | a comment on A1 (dependent pair) | `DELETE /authors/a1` | 204; the comment goes with A1, as today |
| E10 | one transaction adds B3 `written_by` A1 and removes A1 | commit | `InUse` naming B3, nothing sent (PD-5) |

Idempotency: a refused delete changes nothing and may be retried as is; it succeeds once the
referrers are gone. A delete that succeeded is retried as today (`NotFound` or `Conflict`).

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Call `referrer_rows` before opening the transaction and refuse on it | Put the guard in `START` (PD-3) | A referrer committed between the read and the delete slips through (DEC-2) |
| Write a second referrer pattern for the guard | Share `READ_REFERRERS`' `WHERE` fragment | The guard and `referrers` would disagree on what a referrer is |
| Count a graph the same transaction removes as a referrer | `?g NOT IN ($removed)` | The aggregate's own graph and a cascade's collection would block every delete |
| Judge a comment referrer with `may` | Use `readable_referrers`, which asks `Discussion.judged` (PD-9) | Its thread audience decides visibility; `may` would name a comment `referrers` hides |
| Add the guard for every remove | Only when `removals.refusing` is non-empty | G-3: unchanged cost and behaviour for unannotated schemas |
| Put referrer names in the 409 `detail` | `InUseProblem` members (PD-11) | The handler strips 409 details; structured members are the contract |
| Annotate an existing toy class | Add `Author` (PD-13) | Existing tests would start failing for an unrelated reason |
| Edit generated models or `problem-types.adoc` | Change the YAML, `make generate`, `make docs-reference` | LinkML is the single source (AGENTS.md, principle 2) |

## Error matrix

| # | Failure mode | How it is detected | Expected handling |
|---|---|---|---|
| 1 | Referrer exists when the delete is applied | Guard fails; diagnosis finds rows | `InUse` / 409 `in-use`; nothing deleted |
| 2 | Version stale and a referrer exists | Diagnosis: version reason first | `Conflict` (409 `conflict`), as today |
| 3 | Referrer removed between the refusal and the diagnosis | Diagnosis finds no rows | `Conflict` "lost a race … retry"; retry succeeds |
| 4 | Referrer committed after the delete applied | Not detected | Deleted; the referrer dangles (RISK-1) |
| 5 | Add in the same transaction refers to the removed refusing root | PD-5 check at commit | `InUse`, nothing sent |
| 6 | Replace in the same transaction drops the link, and removes the target | Guard sees the stored link | `InUse`; do it in two commits (documented) |
| 7 | Annotation value other than `refuse` | Hard check, `ALLOWED_ANNOTATIONS` | `rp-generate` (`make generate`) refuses the schema, naming the class and the value |
| 8 | Only unreadable referrers | `readable` returns none of them | 409, no `referrers`, `hidden_count` = their number |
| 9 | Referrer is a comment by a non-dependent link | `Discussion.judged` | Named when the caller sees it in its thread, else counted hidden, as `referrers` does; full reach names it |
| 10 | Cascade member of a refusing class referenced from outside | Guard on that member | Whole cascade refused, `InUse(iris=(member,…))` |
| 11 | Session opened without `removals` (consumer's own `open_session`) | — | No refusal: documented, like `keys` |
| 12 | Store not reachable during the diagnosis read | `StoreUnavailable` from `referrer_rows` | Propagates as 503, as every diagnosis read |
| 13 | `UnitOfWork.commit(batches=True)` removes a refusing root in one batch and its referrer in a later one | Guard of the earlier batch | `InUse` from that batch; earlier batches stay committed, as batches are not one transaction today; documented: remove referrers first, or stay within `max_roots` |
| 14 | A part of the removed aggregate refers to its own root | Its graph is in `$removed` | Not a referrer; removed (anti-pattern 3) |
| 15 | A consumer retry loop catches `Conflict` and retries | `InUse` is a `Conflict` | The retry fails the same way until referrers go; the how-to says not to retry on `InUse`, as for `KeyConflict` |

## Test cases

| ID | Tier, file | Input | Expected | Edge |
|---|---|---|---|---|
| TC-1 | generator unit, `tests/generator/unit/test_hard_check.py` | `rp_on_referenced_delete: refuse` / `cascade` | accepted / one problem naming the value | value in quotes |
| TC-2 | unit, `tests/unit/schema/test_schema_structure.py` | toy view | `refusing_classes` = {`lib:Author`} | an `is_a` subclass of an annotated class is included; a class mixing in an annotated mixin is not (PD-2) |
| TC-3 | unit, `tests/unit/persistence/test_session_referenced_removal.py` | E1, E3, E4 on the fake store, `removals` with `refusing={Author}` | E1 `InUse`, graph still there; E3, E4 removed | root typed with two classes, one refusing; matrix 14 |
| TC-4 | unit, same file | E10; error matrix 2, 3, 6, 13 | as the matrix says | 13 through `UnitOfWork` with `max_roots` 1 |
| TC-5 | unit, same file | session without `removals` | no guard in the request text | |
| TC-0 | unit, `tests/unit/core/test_exceptions.py` | `InUse(…, iris=(A1,), referrers=…, more_count=1, hidden_count=2)` | fields kept as given, sorted tuples; `isinstance(e, Conflict)` | empty `referrers` |
| TC-6 | unit, `tests/unit/collaboration/test_referenced_removals.py` | rows of E1, E2, E5, matrix 9 (a comment seen in its thread, one not) | names, `more_count`, `hidden_count` as the table | `max_named_referrers` 0 |
| TC-7 | unit, `tests/unit/collaboration/test_collaboration_referrers.py` (unchanged) | existing cases | pass after the PD-8 move | |
| TC-8 | unit, `tests/unit/collaboration/test_collaboration_cascade.py` | E6, E7 | as the table | member already gone |
| TC-9 | unit, `tests/unit/api/test_problems.py` and a new `tests/unit/api/test_delete_in_use.py` | E1, E2, E3 through the toy app | 409 body validates as `InUseProblem`; 204 | `If-Match` stale → 409 `conflict` |
| TC-10 | unit, `tests/unit/api/test_contract.py` | OpenAPI of the toy | `DELETE /authors/{id}` 409 references `InUseProblem`; `/books` does not | |
| IT-1 | integration, `tests/integration/store/test_referenced_removal.py` (Fuseki) | 20 rounds: B1 refers to A1; concurrently remove B1 and remove A1 | per round: A1's graph and registry entry are wholly there or wholly gone (never partial); a returned A1 removal means B1 is gone; a raised one leaves A1 whole and is `InUse` (naming only B1) or a plain `Conflict`; the outcome counts are in the failure message, no mix required. IT-1b (same file, B1 kept): 20 concurrent removals of A1 are all `InUse` and A1 stays whole, which fails without the guard (D-11) | — |
| IT-2 | integration, same file | E1 and E7 on Fuseki | as the table | the guard's SPARQL runs on the real store |
| IT-3 | integration, same file | E8, E9 and matrix 14 on Fuseki | E8 refused; E9 and matrix 14 removed | the dependents filter and the `NOT IN ($removed)` exclusion inside the guard on the real store |

The scenarios of `specs/rp-reverse-references/spec.md` map to TC-9 (E1, E2, E3), TC-3 (E4) and
TC-8 (the two cascades); those of `specs/rp-service-api/spec.md` to TC-9 and TC-10; rows go to `tests/audit/scenario-map.csv` through `make refresh-map`. No test is moved;
TC-7 is the existing unit-lane suite, which keeps proving `referrers` after PD-8.

## Risks / Trade-offs

- **RISK-1** (likely over time, medium impact): a write committed after the delete may name the
  deleted IRI; nothing in the toolkit checks that a referenced aggregate exists. The guarantee is
  exactly G-1 and the narrowed DEC-2: no referrer at the moment the delete applies. *Accepted by
  the owner* (2026-11-20, `inputs/qa.md`), stated in the how-to; a write-side check would be its
  own EPIC.
- **RISK-2** (unlikely, high): the guarantee rests on the store applying one update request
  atomically, the assumption of every version and key guard (transactions PD-2). IT-1 checks it on
  Fuseki. *Accepted*, inherited.
- **RISK-3** (likely, low): a popular aggregate's diagnosis reads all its referrer rows. Only
  after a refusal, and the read `referrers` already does. *Accepted*.
- **RISK-4** (medium, low): a collection that names an aggregate blocks its deletion (E8);
  consumers may find it surprising. Documented; decided (OPEN-2).
- Trade-off: PD-5 refuses "drop the link and delete the target" in one commit. Two commits work.

## Open Questions

None. The owner accepted every recommendation on 2026-11-20 (`inputs/qa.md`):

| ID | Decision |
|---|---|
| OPEN-1 | A cascade with a refusing member referenced from outside it is refused whole (PD-12). |
| OPEN-2 | A collection's `had_member` link is a referrer like any other (E8). |
| OPEN-3 | A `rp_writes: service` class may carry the annotation; its `session.remove` refuses; the hard check accepts the combination. |
| OPEN-4 | Added: `specs/rp-service-api/spec.md` (the `in-use` problem) and the two cascade scenarios in `specs/rp-reverse-references/spec.md`. |

## Delivery decisions

Taken by the lead during delivery (rule R-0007); shown to the owner for validation at the end.

| ID | Decision | Why |
|---|---|---|
| D-1 | The stages are built in parallel worktrees (owner, 2026-11-20: "advance in parallel"): stage 2 on `feat/delete-refuses-referenced-s2` from task 1.1's commit, stage 3's docs on `docs/delete-refuses-referenced-s3` written to the PLAN ahead of the code. Each is rebased on `develop` after the stage before it merges, and the docs are checked against the built code before their PR. | Tasks 2.1 and 3.1 touch none of stage 1's files; the code chain from 2.2 on stays sequential. |
| D-2 | `hard.py` imports the generated `OnReferencedDelete` and is itself a generation input, so task 1.1 was generated twice: once without its `ALLOWED_ANNOTATIONS` row, then with it. | The generator cannot import an enum it has not generated yet. |
| D-3 | `problems.py` got its `in-use` title and status row in task 1.1, and `InUse` its problem mapping in task 2.1; task 2.3 adds the `InUseProblem` body. | `problems.py` looks up every slug at import, and the table test requires a row per error class: a commit must not leave the gate red. |
| D-4 | Task 1.2 also updated about ten existing tests that hard-code the toy's classes, `Book.slots` and routes (lock, boundary, frames, OpenAPI, documents, allowed actions, shape snapshot). | PD-13 kept existing behaviour; these tests list the toy's shape, not its behaviour. |
| D-5 | Tester: no. The PLAN has no `## Invariants` section and the appetite is MEDIUM (stage loop, Prepare). Stage review per P-0005: one L2+L3 pass per stage; the full review (L1, L2, L3 separate, L4+L5 one) once, on the last stage. | The repository rule overrides the default MEDIUM set. |
| D-6 | Stage 1 review (L2+L3, PR #224): no Critical. Under the floor: W1 (no test of `max_named_referrers` minimum 0), W2 (the map's evidence named TC-2 docstrings the tests lack; the lead corrected the map rows to "name + covered code"), S1 (no test of OPEN-3's `rp_writes: service` + `refuse`), S2 (the annotation on a non-root class is accepted and does nothing: an owner question for the full review). Checker: pass; its three findings (a trace line without a decision id, the sign-off line inside the 1.1 commit, D-6 before D-5) are under the floor, the last fixed here. | The floor: only Critical findings are fixed in a stage. |
| D-7 | Owner, 2026-11-20, on task 2.2's HIGH impact (`Transaction`: 19 direct, 37 in all): proceed, with the adversarial tester right after 2.2 attacking the guard (concurrency, batches, self-reference, matrix rows 2, 3, 6, 13, 14). Amends D-5 for stage 2. | The owner's choice; the guard sits under every commit. |
| D-8 | Stage 2 built in parallel (owner, "work in parallel with subagents"): 2.3 split into (a) `readable_referrers` and `ReferencedRemovals`, (b) the problem handler and route contract, (c) the kit and route wiring; 2.3a, 2.3b and 2.5 on their own branches, folded into `feat/delete-refuses-referenced-s2`. A collection's link is its `has_part` slot: E8 and the docs say `had_member` by mistake; the code names the slot from the schema, so E8 reads `(S1, Shelf, has_part)`. | Disjoint files; the naming is the schema's, not a decision. |
| D-9 | Tester finding D-T-1, accepted and re-labelled **Critical**: the same-commit check (PD-5, `_link_rows`) ignores the session's `dependents` pairs, which the store guard honours, so a commit that removes an author and adds a comment on it is refused while the same comment stored earlier does not block (E9). Decision: PD-5 skips the dependents pairs exactly as the guard does. | Two definitions of a referrer, the first anti-pattern of this design; a dependent record must never block (E9). |
| D-10 | Security finding (automated commit review, MEDIUM, accepted as **Critical**; owner, 2026-11-21: "fail closed at HTTP"): an `InUse` raised without a `readable` callable names every referrer, and the 409 handler would show them to a caller of a consumer route that removes without `readable` (`kit.remove_with_files`, `session.remove`). `InUse` records whether a `readable` callable filtered its referrers (`filtered: bool`, set by `ReferencedRemovals.in_use`); the handler answers an unfiltered `InUse` with `referrers: []`, `more_count` 0 and every referrer aggregate in `hidden_count`. In-process callers keep the full names (E5 unchanged). `remove_with_files` takes an optional `readable=`. Amends PD-9 and PD-11 at the HTTP boundary. | An answer must never name what the caller may not read (DEC-3); failing closed protects every route, including ones the toolkit does not own. |
| D-11 | Stage 2 review (L2+L3, PR #225): W1 re-labelled **Critical**: IT-1 cannot fail (B1 is always removed, so "A1 never gone while B1 stays" holds with no guard at all), and IT-1 is the only check RISK-2 names. IT-1 is corrected: each round races a removal of A1 against a removal of its referrer B1 and asserts what a non-atomic store could break: A1's graph and its registry entry are either wholly there or wholly gone; an A1 removal that returned is consistent with B1 gone before it (an A1 still there was refused with `Conflict`); and A1 refused while B1 still exists is `InUse` naming B1. Under the floor: W2 (no test of `KeyConflict` before `InUse`, PD-4), S1 (the route opens a collaboration for every DELETE; open it only for a refusing class), S2 (`in_use_problem` docstring), S3 (the `in-use` slug description in the YAML), S4 (no test that the PD-5 type read is skipped). | A test that cannot fail checks nothing; the owner's RISK-2 acceptance rests on it. |
| D-12 | Fixer finding, out of scope: a commit that adds a dependent record on a root and removes that root loses the record and raises a misleading `Conflict`, with or without the refusal (it predates this change). Filed as #226; D-T-1's test asserts only "not `InUse`, the root removed" (it passes whether the commit raises `Conflict` or succeeds; pinning the outcome is in #227). Second automated security finding, accepted as **Critical** with D-9's reason: the same-commit check judged one class per root, the guard every `rdf:type`; it now drops a dependent link only when every type of the root forms the pair. | Out-of-scope defects become issues, not code here; one definition of a referrer. |
| D-13 | Full review (P-0005: L1, L2, L3 separate, L4+L5 one), on the whole EPIC at 003f1ee6 and the stage-3 docs: **no Critical**. Docs findings (L2 W1–W3, L3 W2: the cost claim, the same-commit comment, `async with kit.collaboration`, the architecture record of the guard) and a cold reader's twelve points are fixed in stage 3's docs. The spec delta's cap wording now says aggregates and states the fail-closed answer (L2 S2); the in-use scenario maps to the router test (L2 S1). Under the floor, filed as #227: L1 S1 (a refused cascade reads all rows of every root), L1 S2 (`Aggregates.remove` docstring), L2 S3 (D-T-1's test pins no outcome), L3 W1 (two modules outside the import contract), L4+L5 W1–W4 (the guard inside `Transaction`, the judged root unnamed, `ReferrerRow` by position, duplicated test helpers) and S1–S7. | Only Critical findings are fixed in delivery; the rest is recorded and tracked. |
| D-14 | The sort of the tester's probes (fix pass, 44bbae42), named here because the stage-2 checker found the record missing. **Kept** (moved by feature into `test_session_referenced_removal.py` and `test_session_referenced_removal_dependents.py`, some renamed): the D-T-1 test; E9's three dependents probes; a refusal changes no quad; a missing root is `NotFound`, not `InUse`; a foreign part blocks; a graph outside the registry and an `rdf:type` statement are no referrers; twelve removed roots each get a guard; a referrer removed with another author frees nothing; replacing the referrer to add the link and a part naming the removed author are refused unsent; a literal equal to the IRI is no link; `readable` raising propagates on both paths; matrix 4 (RISK-1 pinned); matrix 13 within one batch and referrer-first. **Deleted, duplicated by the builder's tests:** matrix 2 one stale root among two; matrix 3 a new referrer named at diagnosis; matrix 6 pointing at another author; an added root linking to its removed neighbour (E10); matrix 13 the first batch refused commits nothing; a shelf removed with a referenced author names only the author; a non-refusing referenced root asks nothing (E4); a refusing-subclass root and a non-refusing-mixin root (the session sees only the refusing set); a toolkit-written referrer root (E1); a session without dependents counts the target; many roots none referenced; referrers removed in the same commit free two authors; two mutually referring roots removed together, and one of them alone (E1); a root linking to itself (matrix 14). **Deleted, weak probes:** a literal or longer IRI (term equality only); a root removed and re-added (accepted any outcome); the seven escaping cases (never reach the guard text: the IRI policy rejects them first); matrix 13 without batches (a size error, not the guard's). Under-the-floor items of D-11 (S1 route collaboration, S2 docstring, S3 slug description) are added to #227. | The PR lists each deleted test with its reason (stage loop, step 4). |
