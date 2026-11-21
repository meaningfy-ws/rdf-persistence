<!-- PLAN (design half) of nested-collections. PLAN = this file + tasks.md.
     Read against develop c671fefb + the collection-has-part change (slot `has_part`, `v.HAS_PART`). -->

# Design: nested-collections

> Derives from: EPIC `nested-collections` (proposal.md), DEC-1 to DEC-3; issue #198.

## Context

A collection names members of one `member_class` (`rp_collections.yaml`); the write guard
(`write_guards.py` `_check_collection`) refuses a member that is not a stored aggregate of that
class or a descendant (`outside_member_class`). A collection of collections exists today only as
a collection whose member class *is* the collection class; `members(deep=True)`
(`reference_collections.py` `_gather`) walks it breadth first, once per collection, so a stored
cycle ends the walk (spec requirement "Collections can contain collections"). Nothing refuses a
cycle on write.

Facts that shape this PLAN:

- F-1: each aggregate lives in its own named graph; `<C> dct:hasPart <M>` sits in C's graph. The
  store has no union default graph (every query names `GRAPH ?g`), so **a SPARQL property path
  cannot follow membership from one collection's graph into the next**. "One property path" is
  not available without changing the store layout (out of appetite).
- F-2: a transaction's guards (`Transaction._guards`) are evaluated by the store at the start of the
  one update request (`START`), against stored data, before any of its operations; the toolkit
  already relies on the store applying update requests one at a time (PD-2 of the session).
- F-3: `WriteGuard.prepare` (the port; `WriteGuards` is its one implementation, which ends by
  calling `Workflows.keep_state`) runs when a change is collected, reads stored data only, and
  cannot add a guard to the request; it does not see earlier changes of the same transaction.
- F-6: a failed request is diagnosed by `Transaction._diagnose` → `_versions_found` (reads the
  versions of `_roots` and `_required`) → `_reasons`, which names a changed root and an absent
  `_required` graph, never a graph whose version merely changed.
- F-7: `Session.graphs_with(predicate, obj: URIRef | None)` cannot ask for a literal object.
- F-4: `delete_cascade` refuses (`_require_of_member_class`) any found member outside the member
  class; a nested collection of a nesting collection would make every cascade fail.
- F-5: an added optional slot needs no schema version or migration (`rp-schema-migrations`,
  scenario "an added optional slot").

## Goals / Non-Goals

**Goals**
- G-1: `nests: true` lets a collection name collections of its exact class and member class (DEC-1).
- G-2: no save, alone or racing another, leaves a nesting cycle stored (DEC-2).
- G-3: `members(deep=True)` (the EPIC's "transitive") lists the items of the whole tree; `hidden_count` counts each
  unreadable named member once, at any level.
- G-4: flat collections and member-class-is-collection-class collections behave as today.

**Non-Goals**
- A property-path read (F-1), ordering, "move", mixed member classes, nesting across classes
  (EPIC no-gos); a cascade that descends (OPEN-1); renaming `deep` (OPEN-2).

## Decisions

- **PD-1 Slot.** `nests` in `rp_collections.yaml`: `slot_uri: rp:nests`, `range: boolean`,
  optional, on `ReferenceCollection`; absent ≡ false. `vocabulary.NESTS = predicate("nests")`.
  `make generate` regenerates the toolkit and the toy library (Shelf gets `nests` via the mixin);
  no schema version and no migration (F-5).
- **PD-2 What a nested member is.** A member N of a collection C is *nested* when N is stored with
  exactly C's collection class (`collection_class`, not a subclass) and N's `member_class` equals
  C's. N's own `nests` may be false (a leaf folder). One helper in `reference_collections.py`,
  `accepted_members(view, collection_class_name, collection) -> set[str]` (class IRIs), replaces
  the bare `member_class_iris` call in the write guard and in `_require_of_member_class` (F-4):
  member class and descendants, plus the collection class itself when `nests` is true. The
  member-class equality of a nested member is checked on its decoded graph.
- **PD-3 Disjoint meanings.** `nests: true` with a member class that is itself a collection class is
  refused (`InvalidBody`, "nests needs a member class that is not a collection"). The existing
  collection-of-collections (cycles allowed, deep read ends them) and nesting (cycles refused) never
  overlap, and a rule member can never be a nested collection (a rule matches the member class
  exactly), so only named members are edges of a nesting tree.
- **PD-4 Cycle check, in memory, in the save.** In `WriteGuards._check_collection`, when the saved
  collection C has `nests` and names nested members:
  1. `new = nested members of C − nested members of C's stored graph` (an add has no stored graph;
     a replace reads them with `session.root_values(C, [v.HAS_PART])`). Empty `new`: no walk, no
     guard (a rename or an item edit is never slowed nor made to conflict).
  2. One query: `session.graphs_with(v.NESTS, Literal(True))` (PD-10 widens its `obj`), decoded and kept when of C's class
     and member class: the tenant's nesting skeleton `{collection: (version, nested members)}`.
     The collections collected earlier in the same transaction overlay it (PD-5).
  3. An iterative depth-first walk from each IRI of `new`, with a visited set; reaching C is a
     cycle. Cost: one query plus O(V+E) over the skeleton; depth is unbounded and costs nothing
     extra (no recursion, no query per level).
  4. Every collection the walk reached is reported through `rely_on(iri, version)` (PD-5): the
     skeleton ones with the version in their graph, and the reached ones outside the skeleton
     (nested members with `nests` false, leaves today) with the version of one
     `session.heads(...)` call. A leaf must be guarded too: a racing save could turn it into a
     nesting collection that names C. A root already collected in this transaction is not
     guarded again (its own replace guard covers it). The commit holds only if none of them
     changed since it was read.
  A cycle raises `InvalidBody` naming C, the member that closes it and the number of collections
  between, never their IRIs (PD-7): `"saving {C} would make a cycle: {C} → {N} → (2 more) → {C}"`.
- **PD-5 Guard context.** In `session.py`:

  ```python
  @dataclass(frozen=True)
  class GuardContext:
      """What a write guard may use of the transaction collecting the change."""
      collected: Mapping[str, tuple[Triple, ...]]  # root IRI -> triples collected before this change
      rely_on: Callable[[str, str], None]          # (root IRI, version read) -> None
  ```

  `WriteGuard.prepare(self, session, iri, triples, stored, allowed_state, *, context: GuardContext)`;
  `Transaction.add_graph` / `replace_graph` build it as
  `GuardContext(collected=MappingProxyType(self._collected), rely_on=self._rely_on)`, where
  `self._collected: dict[str, tuple[Triple, ...]]` gets the prepared triples of each add and
  replace right after `_collect` (a remove adds nothing). `Transaction._rely_on(iri, version)`
  calls `_require_open()`, appends `_at_version(self._session._graph(iri), version)` to `_guards`
  (the existing `_AT_VERSION` fragment: constants only, no `?var$n`, so it needs no number and joins
  no other guard), and records `self._relied[graph] = (str(iri), version)`; a second call for the
  same graph with the same version is a no-op, with another version a `ValueError`. Inside
  `WriteGuards`, only `_check_collection` uses `context`; the `keep_state` call is unchanged. This
  is a port change: the task gate is `make test-fast check-quality`.
- **PD-9 Naming a relied-on graph in the Conflict** (F-6). `_versions_found` reads the graphs of
  `_roots`, `_required` and `_relied`; `_reasons` adds, for each `(graph, (root, version))` of
  `_relied` whose found version differs from `version` (`None` included),
  `reasons[root] = changed_text(root, found)`. The `Conflict` thus names it in `iris` and in its
  text ("… was changed by someone else since it was read").
- **PD-10 `graphs_with` takes a literal** (F-7). Its signature becomes
  `obj: URIRef | Literal | None = None`; `term(obj)` already renders a literal. No caller changes.
- **PD-11 Logged deviation from the EPIC's preference (Rabbit-holes: "one SPARQL property path is
  preferred").** It is not taken, because of F-1: membership triples are in each collection's own
  graph and no union default graph exists, so a path stops at the first graph. Changing the store
  layout or enabling a union graph is out of the SMALL appetite and touches every query. The read
  walks breadth first (PD-6) and the cycle check walks one skeleton read in memory (PD-4). The bet
  holds (the EPIC asks for the behaviour, not the query form); this is a PLAN-level change, not a
  re-shape. Recorded in `inputs/qa.md`.
- **PD-6 Transitive read.** `members(collection, *, deep=False)`: the existing flag, not renamed
  (owner, OPEN-2), so no caller breaks; `deep=True` is what the EPIC calls `transitive=True`.
  It reuses `_gather` breadth first, one `get_graph` per readable nested collection plus one `find`
  per ruled collection (F-1 rules out one path query). It descends into a member when the walked
  collection has `nests` and the member is nested (PD-2), or, as today, when the member class is a
  collection class. Nested collections of a nesting collection are structure: not listed in
  `member_iris`, not counted. Every other named member of every visited collection is listed if
  readable, else counted once in `hidden_count`; an unreadable nested collection is counted once
  and not entered (nothing about its content leaks). A stored nested member whose member class
  differs is `StoredDataInvalid` through `_stored_valid`, as other untrusted stored data.
- **PD-7 What a refusal may name.** The saver holds C and the members it names; intermediate
  collections may be hidden from it, so the message names only C and the closing member and counts
  the rest (consistent with RISK-8 of the write guards, nothing more disclosed).
- **PD-8 Cascade and collections_of.** `delete_cascade` deletes the direct members only, a nested
  collection as a member with its own members kept, as the spec says today (OPEN-1); PD-2 makes it
  accept nested members. `collections_of(N)` needs no change: the referrer row of `has_part` from
  a collection class already names the parent; a test proves it.

## Algorithm / approach

Worked example (Shelf, member class Book, all `nests: true`): stored `library ⊇ {b3, poetry}`,
`poetry ⊇ {b1, b2}`.
- Save `poetry` with `has_part = {b1, b2, library}`: `new = {library}`; skeleton walk
  `library → poetry` reaches C → `InvalidBody` "saving poetry would make a cycle: poetry → library
  → (0 more) → poetry".
- `members(library, deep=True)` → `[b1, b2, b3]`; reader without `read` on `poetry` →
  `[b3]`, `hidden_count = 1`; without `read` on `b1` → `[b2, b3]`, `hidden_count = 1`.
- Race: T1 saves `x` adding `y`, T2 saves `y` adding `x`, both collected before either commits.
  T1 relies on `y@v0`, T2 on `x@v0`. T1 commits; `x` is now `v1`. T2's request starts, guard
  `x@v0` fails → `Conflict(iris=[x])`; nothing written. T2 re-reads, saves again, gets `InvalidBody`.
  Why it is enough: after both commits a cycle C → N → … → C must pass a first collection whose
  edge was added concurrently; every collection before it was unchanged, so the walk reached it
  (as a skeleton node or as a leaf) and relied on its version, and its guard fails (F-2). The
  attack that found the leaf case: T1 adds leaf N to C, T2 turns N into a nesting collection
  naming C and commits first; without a guard on N both would commit.
- Same transaction: `replace(x, +y)` then `replace(y, +x)`: the second `prepare` sees `x`'s collected
  triples in `context.collected`, finds the cycle, refuses.

Idempotency: a save is a guarded replace as today; a retried save after a `Conflict` re-runs the
check from fresh reads. Reads write nothing.

### Anti-patterns
| Don't | Do instead | Why |
|---|---|---|
| Walk the tree with one query per level in the write guard | One `graphs_with(v.NESTS, true)` read, walk in memory | depth would cost round trips inside the save |
| Check the cycle after the commit | Check in `prepare`, guard the read versions in the request | DEC-2; a stored cycle would need a repair |
| Guard every collection of the tree on every save | Guard only what the walk from *new* nested members visited | an unrelated sub-folder edit would conflict a rename |
| Name intermediate collections in the refusal | Name C and the closing member, count the rest | PD-7, hidden collections |
| Add a `transitive` flag beside `deep` | The one existing `deep` flag (OPEN-2) | two overlapping flags; no caller breaks |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| C names itself (replace, `nests`) | walk from `new = {C}` reaches C at once | `InvalidBody` naming the cycle |
| C names itself on add | `heads` finds no stored C | `InvalidBody` "not stored aggregates" (today's rule) |
| 2- or 3-cycle through stored collections | walk over the skeleton | `InvalidBody`; nothing stored |
| Two racing saves that together close a cycle | `rely_on` version guard fails at request start; `_reasons` names it (PD-9) | `Conflict(iris=[the changed one])`; nothing stored; a retry gets `InvalidBody` |
| A racing save turns a reached leaf N (`nests` false) into a nesting collection naming C | N's version guard (PD-4 step 4) | `Conflict` naming N |
| A save sets `nests` false on a collection that still names nested ones | today's member-class check | `InvalidBody`; the tree stays as stored |
| Cycle closed by two changes of one transaction | overlay of `context.collected` | `InvalidBody` at the second collect |
| Nested member of another member class | PD-2 equality on its decoded graph | `InvalidBody` "not stored aggregates of Book" (today's wording) |
| Nested member of a subclass or another collection class | exact-class test, PD-2 | `InvalidBody` as above |
| `nests` with a collection class as member class | PD-3 | `InvalidBody` |
| Collection with `nests` false names a collection | today's member-class check | `InvalidBody` (unchanged) |
| A collection on the walked path is deleted before commit | its version guard: graph absent | `Conflict` naming it |
| Unreadable nested collection in a deep read | `_may(READ)` false | counted once, not entered |
| Stored nested member with another member class (bypassed write) | decode in `_gather` | `StoredDataInvalid` via `_stored_valid` |
| Cascade of a nesting collection | PD-2 accepted classes | nested collections deleted as members, their members kept |

## Risks / Trade-offs

- **RISK-1 Concurrent cycle.** Likelihood low, impact medium (a stored cycle). Mitigated by PD-5:
  closed as long as the store applies one update request at a time with its guards (F-2), the
  assumption every guarded write of the toolkit already makes. A store that evaluated guards
  without that isolation would let it through; accepted, as for all guarded writes.
- **RISK-2 Skeleton size.** `graphs_with(v.NESTS, true)` reads every nesting collection's whole
  graph, items included, on each save that adds a nested member. Likelihood low (the consumer's
  collections are "few"), impact: slow saves of sub-folders in a large tenant. Accepted for SMALL;
  if measured slow, a narrower read (root `has_part` objects only) is a follow-up.
- **RISK-3 False conflicts.** A save that adds a sub-folder conflicts with a concurrent edit of any
  collection under it. Likelihood low, impact a retry. Accepted (PD-4 step 1 keeps it to saves
  that add nesting).
- **RISK-4 Transitive read cost.** N+1 reads for N readable nested collections (F-1). Accepted;
  the walk stops at unreadable ones and visits each once.

## Open Questions

None. The owner decided all four on 2026-11-20 (`inputs/qa.md`):

- **OPEN-1 → decided:** `delete_cascade` deletes direct members only (PD-8).
- **OPEN-2 → decided:** keep `deep=`; no rename, so existing callers do not break (PD-6). The
  EPIC's and the issue's `transitive=True` is written `deep=True` in the spec delta.
- **OPEN-3 → decided:** a nested collection may have `nests: false` (PD-2).
- **OPEN-4 → decided:** `members(C, deep=True)` lists items only; `members(C)` lists sub-folders (PD-6).

## Delivery decisions

- **D-1 Build order and joins (2026-11-21).** One stage, built by parallel builders in their own
  worktrees and joined by merge: 1.1 ∥ 1.3, then 1.2, then 1.4 ∥ 1.5 ∥ 1.7, then 1.6 ∥ the
  adversarial tester. `develop` was merged in at the start (it held `delete-refuses-referenced`
  stage 2, #225, which touches the same guards); `make generate` after the merge changed nothing.
- **D-2 The walk stays in the write guard.** PD-4's walk first landed as a module `nesting.py` with
  two hand-written dataclasses; the model guard and the layout check refuse both. It is now the
  private `_walk_from` of `write_guards.py`, returning plain values. The 1.4 builder's gate had not
  run to the end (T1); the lead's run on the joined head found it.
- **D-3 Tester findings (task 1.4, `test_collaboration_nesting_adversarial.py`).** Six defects, each
  pinned by an `xfail(strict=True)` test. Fixed in the fix pass:
  - T-1: a graph relied on at two versions in one transaction (it changed between two reads) raised
    `ValueError`; it is a `Conflict` naming it. This reverses PD-5's `ValueError`, which assumed
    the two reads could not differ.
  - T-2: a stored nesting collection that does not decode blocked any save that walked the skeleton
    and was named in the refusal (PD-7); it is skipped.
  - T-3: a stored leaf (`nests` false) that names a shelf, written past the guard, turned into a
    nesting collection with the same members was not walked; stored members count as already
    nested only when the stored collection nests.

  Under the floor, the tests stay `xfail(strict=True)`:
  - T-4: the same-transaction overlay ignores removes, so a cycle through a collection removed
    earlier in the transaction is refused. The error is on the safe side; a retry after the commit
    succeeds.
  - T-5: `delete_cascade` deletes a stored nested collection of another member class (written past
    the guard) where a deep read raises `StoredDataInvalid`. PD-8 says the cascade deletes members;
    only data that bypassed the guard reaches it.
  - T-6: the "(k more)" of the cycle refusal counts the first way back the walk meets, not the
    shortest. Cosmetic.

  Not tested: a subclass of a collection class (the toy library has none, and the tester does not
  edit schemas); the exact-class rule is enforced by `accepted_members` adding only the class's own
  IRI. Also not tested: a sub-collection held by two nesting parents, which nothing refuses (the
  how-to says so; the cold reader asked).
- **D-4 Review findings (SMALL: one pass, L2 + L3; nine findings).** Accepted, one fix pass:
  - C-1 (Critical): a replace of a nested collection could change its `member_class`, which broke
    the parent's deep reads and refused every later save of the parent. A replace that changes the
    member class of a collection a nesting collection of its class holds is refused.
  - W-4, re-labelled Critical because it sits on C-1's path: every save of a nesting collection read
    the graph of every nested member. With C-1 fixed, stored nested members stay valid, so only the
    new ones are read (PD-4 step 1: a rename is not slowed).
  - W-5, with C-1 (same function): the T-3 rule in `_stored_members` is an early return.
  - W-2, re-labelled Critical because it departs from a decision (PD-32 item 5 of the session): the
    new private piece `_rely_on` is pinned by `test_private_transaction_pieces.py`.
  - W-1, re-labelled Critical because the docs are untrue of the code: the architecture pages said a
    write guard adds no guard to the request; they now describe `GuardContext` and `_rely_on`.
  - W-3, re-labelled Critical because the map is a gate: one spec scenario had no row and two tests
    mapped to the wrong scenario.

  Under the floor: S-1 (arguments threaded through three methods), S-2 (the exact-class test and
  the triples-to-graph loop repeated), S-3 (a static method that calls another by class name). C-1's
  check costs every replace of a collection one `graphs_with` query for its holders.
- **D-5 Security review of the C-1 fix (automated, two findings).** Fixed: a nesting collection
  that changed its own member class kept its stored nested members unchecked (W-4 skipped them);
  they are skipped only when the stored member class is the new one. Fixed: C-1's search for holders
  ignored the collections collected earlier in the same transaction; it overlays them as the cycle
  check does. Accepted as a risk, like RISK-1: across two transactions, T1 changes the member class
  of S (it found no holder) while T2 makes a nesting collection hold S, and T2 commits first. T1 has
  nothing to rely on (version guards cannot state that a holder is absent), so both commit, and deep
  reads of the holder raise `StoredDataInvalid` until a replace puts S's member class back. In the
  other order T2 relies on S's version and gets a `Conflict`. Likelihood low (a member-class change
  racing a nesting save of the same collection); a guard on absence is a follow-up if it is ever
  seen.
