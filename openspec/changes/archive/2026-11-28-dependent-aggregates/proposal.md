<!-- Parents: GitHub issue #437 A.5 (../aggregate-composition/inputs/seed.md); the change
     aggregate-composition (DEC-1, DEC-7); the living capabilities rp-aggregate-store,
     rp-uml-import, rp-service-api, rp-reverse-references. Q&A: inputs/qa.md. -->

# EPIC: Dependent aggregates, stored on their own and deleted with their whole

**Golden-thread parents:** issue #437 A.5 (an «own graph» part: its own named graph and version
token, written on its own, deleted with its whole); `aggregate-composition` DEC-1 and DEC-7 (this
change lifts its refusal of a generated «own graph» part); `rp-aggregate-store` "One named graph per
aggregate" and "Several aggregates of one tenant commit atomically"; `rp-reverse-references` "A
class may refuse deletion while referenced". **Serves:** the first consumer's S8-14 (results
written by parallel workers, deleted with their run); it names this change id.

## Appetite

**MEDIUM.** One new capability, the dependent aggregate: a metamodel annotation, a write guard,
the delete cascade in the session, the converter output that `aggregate-composition` refuses
today, and their tests and docs. The service API, events and access are touched lightly.

## Why

Some data is part of a whole in meaning but is written apart from it: several workers each write
their own result under one run, at their own time, and none should conflict on the run's version
token. Today a consumer has two bad options. It can make each result its own aggregate and write
the delete cascade itself, which the consumer's AG-6 exception does now. Or it can inline the
results in the whole, which makes every worker rewrite the whole. The toolkit should store such a
part as an aggregate of its own and still guarantee that it never outlives its whole.

## Solution outline

A class annotated as **dependent** on a whole is an aggregate in every respect: its own named
graph, version token, `rp_path`, API resource and access. It also holds a required pointer to its
whole, fixed at creation. Creating or replacing a dependent part checks, in the same atomic update,
that the whole still exists and is of the whole's class. Deleting a whole deletes its dependent
parts transitively in the same transaction, so a part's own loaded graphs and dependent parts go
with it: all or nothing, with the whole's delete right alone. The converter emits the annotation
and the pointer for an «own graph» composition whose part is a generated class, lifting the
refusal from `aggregate-composition`.

## Key decisions

- **DEC-1**: the part points to its whole. The pointer is the association's inverse role, a
  required single-valued slot, and the class carries the annotation `rp_dependent_on: <slot>`. A
  part is written without touching the whole, so parallel writers never conflict on the whole's
  version. Rejected: the whole listing its parts (every part write rewrites the whole); pointers
  both ways. (Q1)
- **DEC-2**: deleting a whole needs the caller's delete right on the whole only; its dependent
  parts go whatever the caller's rights on them, because a part cannot exist without its whole.
  This differs on purpose from `delete_cascade` of a reference collection, whose members exist on
  their own. Rejected: a right on each part. (Q2)
- **DEC-3**: a write of a dependent part checks, inside the same update, that its whole exists and
  is of the annotated class. If not, it is `NotFound` and nothing is written. Changing the pointer
  after creation is a `Conflict`. — A worker that finishes after its run was deleted leaves no
  orphan. Rejected: a periodic orphan sweep; the plain reference check, which misses a concurrent
  delete. (Q3)
- **DEC-4**: the cascade is all or nothing. It is transitive (a dependent part's own dependent
  parts and loaded graphs go too) and counted against the mapper's `max_roots` before anything is
  written. Above it, the delete is `CommitTooLarge` with the limit in the message, as
  `delete_cascade` does. Rejected: deleting in batches. (Q4)
- **DEC-5**: a dependent part is not a pointer target from outside its whole's aggregate
  (`aggregate-composition` DEC-8 already refuses such a pointer in the model). A stored referrer
  found at delete time that is not part of the cascade refuses the whole delete with `InUse` when
  the part's class says `rp_on_referenced_delete: refuse`, as the reference-collection cascade
  does.
- **DEC-6**: a delete of a whole publishes one deleted event per aggregate it removes (the whole
  and each part), in one commit, as any multi-aggregate transaction does today.
- **DEC-7**: `rp-generate` refuses a schema in which a dependent class's pointer slot is not
  required, not single-valued, or does not range over a served root, and refuses a cycle of
  dependence.

## Rabbit-holes

- **Moving a part to another whole.** Refused (DEC-3); it is a delete and a new write.
- **Listing a whole's parts.** No new endpoint. The existing listing filter on the pointer slot
  serves it (`rp-service-api` "Listings are filtered and paged").
- **Very wide wholes.** A whole with more parts than `max_roots` cannot be deleted in one call;
  the consumer raises the limit or deletes parts first. No batching (DEC-4).

## No-gos

- No change to reference collections or their `delete_cascade`.
- No inline (non-«own graph») composition change: inlined parts stay in their whole's graph as
  today.
- No orphan sweep or repair tool.
- No migration of existing consumer data. A consumer replaces its own cascade code itself.
- No new API endpoint for a whole's parts.

---

## What Changes

- Metamodel annotation `rp_dependent_on` on an aggregate root class, naming its pointer slot.
- `rp-generate` checks a dependent class's pointer slot and the dependence graph.
- Session: a dependent part's write checks its whole in the same update and fixes the pointer; a
  whole's delete cascades to its dependent parts, transitively, all or nothing.
- Converter: an «own graph» composition to a generated part emits the part as a root with the
  pointer and the annotation (lifts `aggregate-composition` DEC-7's refusal).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rp-aggregate-store`: dependent aggregates (write guard, cascade delete).
- `rp-metamodel`: the `rp_dependent_on` annotation.
- `rp-generation`: the schema check for dependent classes.
- `rp-uml-import`: «own graph» composition to a generated part.
- `rp-service-api`: a whole's delete cascades; a dependent part's write may answer `NotFound` for
  its whole.

## Impact

- Code: `rdf_persistence/core` (metamodel, generated), `rdf_persistence/persistence/services`
  (session, unit of work), `rdf_persistence/schema/services` (structure),
  `rdf_persistence_generation/` (check, converter), tests in every tier, containers lane for the
  store.
- Docs: the aggregate store how-to and the UML guide.
- Consumers: the first consumer replaces its own cascade (its AG-6 exception) by the annotation.

## Reconciliation (as delivered, 2026-11-28)

| Shaped item | State | PR | Notes |
|---|---|---|---|
| The part points to its whole; `rp_dependent_on` (DEC-1) | delivered | #446 | D-6: `DependenceLink` lives in the core model. D-9: `limits` replaces the removed `max_roots` keyword. |
| The whole's delete right is enough (DEC-2) | delivered | #450 | D-1: delete validators run in the cascade. PD-10: unreadable parts are never named, and D-13 extends this to `NotFound` and `Forbidden`. |
| A write checks the whole; the pointer is fixed (DEC-3) | delivered | #450 | D-8: `NotFound` carries no `iris`. |
| All or nothing, transitive, `max_roots` (DEC-4) | delivered | #450 | D-10: discovery counts parts, not rows. D-11: one linear late-part guard. D-3: starvation is accepted, and the caller retries. |
| `InUse` for a refusing part (DEC-5) | delivered | #450 | |
| One activity, one removal per aggregate (DEC-6) | delivered | #450 | D-2 |
| `rp-generate` checks (DEC-7) | delivered | #446 | D-7: a mixin's annotation does not count. |
| Converter emits the dependent root | delivered | #452 | D-12 |
| On Fuseki (RISK-1) | delivered | #450 | IT-D1 to IT-D5 and a conformance scenario |

Reviews: per-stage L2+L3 passes, checkers, an adversarial tester after the cascade, and the
end-of-epic full review (D-13). Their floor is issue #453. Accepted by the developer on 2026-11-28,
with two decisions standing as delivered (`evidence/acceptance.md`).
