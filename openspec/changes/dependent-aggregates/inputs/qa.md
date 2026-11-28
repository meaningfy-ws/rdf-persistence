# Q&A record: dependent-aggregates (secondary; never groomed)

Shaped with the developer, 2026-11-28, from #437 A.5 (`../../aggregate-composition/inputs/seed.md`)
and the decisions of `aggregate-composition` (its `inputs/qa.md`, Q1, Q2, Q6).

## Facts read before asking

- `Session.delete` removes an aggregate's graph, its loaded graphs and its registry entries.
- `ReferenceCollections.delete_cascade` deletes a collection and its members in one transaction,
  all or nothing, refusing with `CommitTooLarge` above the mapper's `max_roots` and with `InUse`
  when a refusing member is referenced from outside; it needs the caller's delete right on each
  member.
- `rp_on_referenced_delete: refuse` guards a referenced class against deletion.

## Round 1 (2026-11-28, answered)

| Id | Question | Answer |
|---|---|---|
| Q1 | Which side stores the whole-part link? | The part points to its whole (the association's inverse role, required), marked by an annotation; a part is written without touching the whole. |
| Q2 | Whose rights does deleting a whole need? | The whole's delete right only; its dependent parts go whatever the caller's rights on them. |
| Q3 | A part written while or after its whole is deleted? | The write checks, in the same atomic update, that the whole exists and is of the whole's class; otherwise `NotFound`, nothing written. The pointer to the whole is fixed at creation (`Conflict` on a change). |
| Q4 | A whole with more parts than `max_roots`? | Refused, all or nothing (`CommitTooLarge`, the message gives the limit), as `delete_cascade` does. |

## Lead's decisions, not asked (2026-11-28; the developer reviews them with the PLAN)

- DEC-5 (`InUse` when a refusing part is referenced from outside the cascade), DEC-6 (one deleted
  event per removed aggregate), DEC-7 (`rp-generate` checks the pointer slot and refuses a cycle of
  dependence): each follows an existing toolkit behaviour (reference-collection cascade,
  multi-aggregate commits, the boundary check).

## Readiness check (lightweight, 2026-11-28): pass

Appetite, why, outline, DEC-1..DEC-7, rabbit-holes and no-gos present; no undecided bet-level item.

## Planner's reading (2026-11-28, from the attack's A-11; the EPIC stays frozen)

- DEC-5's "a dependent part is not a pointer target from outside its whole's aggregate
  (`aggregate-composition` DEC-8 …)": DEC-8 refuses pointers to *owned* classes, not to dependent
  roots, so a dependent root is a legal pointer target. A refusing part referred to from outside
  refuses the whole's delete (`InUse`); a non-refusing one leaves a dangling reference, as any
  deleted root does. See `design.md` Context and PD-8.
