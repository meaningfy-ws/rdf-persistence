EPIC: nested-collections (proposal.md), issue #198, after collection-has-part. Decisions: design.md PD-1 to PD-11, DEC-1 to DEC-3; owner answers in inputs/qa.md.

Every task: the failing test first, in the tier named; task gate `make test-changed check-quality`
(`make test-fast check-quality` for 1.3, a port change); commit body `Refs: nested-collections
<task> <PD>`. Builders never commit; the lead does. Starts only once `collection-has-part` is
merged into `develop`. One stage.

## 1. Stage 1: nesting collections

- [ ] 1.1 Slot (PD-1). Unit, first: `tests/unit/collaboration/test_collaboration_nesting.py`
  `test_a_shelf_without_nests_does_not_nest` (absent ≡ false after a round trip) fails on the
  missing field. Then `nests` in `rp_collections.yaml`, `vocabulary.NESTS`, `make generate`,
  `tests/toy.py` `shelf(iri, *, nests=False)`. Accept: `make check-generated` clean; the generator's
  lock check asks for no migration.
- [ ] 1.2 Write guard membership (PD-2, PD-3). Unit, first, in the same file, one parametrized
  table (positive and negative per rule): a nested Shelf of Book accepted; refused, as
  `InvalidBody`: nested of another member class, a subclass collection, `nests` false naming a
  shelf, `nests` with member class `Shelf`; flat shelf unchanged. Then `accepted_members` and its use
  in `_check_collection`. Accept: spec scenarios "a nested collection" (save half), "another
  member class" and "nesting over a collection member class" pass.
- [ ] 1.3 Transaction pieces (PD-5, PD-9, PD-10), a port change. Unit, first, in
  `tests/unit/persistence/test_session_transaction.py` (the `graphs_with` case in
  `test_session_graphs_with.py`): `_rely_on(x, v0)` then a
  replace of x by another session before commit → the commit raises `Conflict` with
  `iris == (x,)` and text "x was changed by someone else since it was read" (fails today: no
  `_rely_on`, and `_reasons` names only absent `_required` graphs); the same with x removed;
  `_rely_on` twice with one version adds one guard, with two versions raises `ValueError`;
  `GuardContext.collected` holds an earlier replace's triples in the same transaction;
  `graphs_with(p, Literal(True))` returns only the roots stating `true`. Then `GuardContext`,
  `_rely_on`, `_relied`, `_collected`, the `prepare(..., *, context=)` port signature and
  `WriteGuards.prepare` (which passes nothing new to `keep_state`), `_versions_found`, `_reasons`,
  the `graphs_with` signature; update the existing `prepare` call in
  `tests/unit/collaboration/test_write_guards.py` (`context` is keyword-only, no default). Accept: those tests pass; `make test-fast check-quality` green.
- [ ] 1.4 Cycle check (PD-4, PD-7), after 1.3. Unit, first: self (replace), 2-cycle, 3-cycle,
  cycle inside one transaction, the race (two transactions collected, then committed in turn: the
  second raises `Conflict` naming the first's collection, and a retry raises `InvalidBody`), the
  leaf race (T1 adds leaf N to C; T2 sets `nests` on N naming C and commits first; T1 gets
  `Conflict` naming N), a replace that adds no nested member adds no guard (count of `_guards`),
  and the refusal text names no intermediate IRI. Then the walk in
  `WriteGuards._check_collection`. Accept: spec scenarios "a cycle", "racing saves" and "a leaf
  race" pass. The adversarial tester runs right after this task (agents.adoc).
- [ ] 1.5 Reads (PD-6, PD-8). Unit, first: `members(deep=True)` lists the items of a 3-level
  tree and not its sub-collections; `hidden_count` for an unreadable item at level 2, an
  unreadable nested collection (counted 1, not entered), an item named at two levels (counted
  once); `collections_of(sub)` gives its parent; `delete_cascade` of a nesting shelf deletes the
  sub-shelf and keeps its books; the existing deep-read tests pass unchanged. Then `_gather` and
  `_require_of_member_class`; `deep` keeps its name (OPEN-2). Accept: spec scenarios of the delta
  and of "Collections can contain collections" pass.
- [ ] 1.6 Integration on Fuseki, `tests/integration/store/test_collaboration.py`: the race of 1.4
  against the real store, and a deep read of a 3-level tree. Accept: `make test-containers`
  passes both.
- [ ] 1.7 Docs: `howto/reference-collections.adoc` gains *Nesting collections* (the flag, the
  cycle refusal, the conflict on a race); the *Deep reads* paragraph says that for a nesting
  collection `deep=True` lists items only. Accept: `make check-docs` passes.
- [ ] 1.8 Lead: `make check-all`, `make test-containers`, the SMALL review set, fixes, the PR,
  CI green, acceptance by the owner, archive.

## Roadmap

1.1 → 1.2 → 1.3 → 1.4 → 1.5 → (1.6 ∥ 1.7) → 1.8

## Verification

`make check-all` and `make test-containers` pass, every scenario of the spec delta has a passing
test, `openspec validate nested-collections --strict` passes, and the PR's CI is green.
