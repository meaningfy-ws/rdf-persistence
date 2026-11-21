<!-- Parents: issue #201 (inputs/seed.md); openspec/specs/rp-reverse-references, rp-service-api,
     rp-aggregate-store. Serves: MWB2 v2-03-project-and-resources task 7.1 (D-12).
     Seeds: inputs/seed.md. Consumer triage in ../uml-to-linkml/inputs/qa.md. -->

# EPIC: Refuse deleting an aggregate others point to (opt-in)

## Appetite

**MEDIUM.** One annotation, an atomic guard in the delete's update request, signature changes on
the delete paths and a problem model.

Re-shaped 2026-11-20 by the owner: SMALL → MEDIUM, the atomic guard needs a guard in the delete's
update, signature changes and a problem model. DEC-2 narrowed in the same re-shape. Record:
`inputs/qa.md`.

## Why

The generic delete removes an aggregate even when others reference it. Today the only way to refuse
is to take over every write of the class (`rp_writes: service`) and rewrite its routes. The
consumer's delete guard on collections needs this before `v2-03`'s last stage.

## Solution outline

A class annotation `rp_on_referenced_delete: refuse` (absent means today's behaviour). Both the
generic `DELETE /{type}/{id}` and `session.remove` then refuse inside the delete's own update request:
a guard there matches the links `referrers` reads (its pattern shared, not reused as a call), and
after a refusal the referrers are read and named. If any exist, they raise `InUse(referrers, hidden_count)`, which the API answers as `409` problem
`in-use`. The problem names the readable referrers (type, IRI, slot; capped, with a count of the
rest) and the count of unreadable ones. Nothing is deleted.

## Key decisions

- **DEC-1:** opt-in per class through an annotation in the metamodel's annotation enum, so the UML
  converter carries it with no change (`uml-to-linkml` DEC-2). Rejected: on for everyone, which
  would change today's behaviour.
- **DEC-2:** the check runs in the delete's update request, so no referrer exists at the moment the
  delete applies; a referrer written after it is not blocked (accepted as RISK-1 in design.md).
  Rejected: a pre-check outside it, which races. (Narrowed in the 2026-11-20 re-shape; it read "a
  referrer added concurrently is either seen or blocked by the same guarded update".)
- **DEC-3:** unreadable referrers are counted, never named, the same as `referrers` today.

## Rabbit-holes

- The interaction with `delete_cascade` on collections: a cascade that deletes a member which is
  itself `refuse`-annotated and referenced from elsewhere. The PLAN states the order and the outcome.
- The cap on the number of named referrers is a setting with a default, not a per-call option.

## No-gos

- No other policies (cascade, set-null, detach).
- No change to `referrers`' own results.
- No refusal of deletes made through `rp_writes: service` routes the application owns.

---

## What Changes

- Metamodel: `rp_on_referenced_delete` annotation (enum `refuse`).
- Delete paths: generic route and session remove check referrers; `InUse` exception; `409 in-use`
  problem type in the OpenAPI.

## Capabilities

### Modified Capabilities

- `rp-reverse-references`: a class may refuse deletion while referenced.
- `rp-service-api`: the `409 in-use` problem.

## Impact

Metamodel, session/unit of work, generic routes, problem catalogue, docs (how-to on deleting).

## As built

Reconciled after stage 2 (PRs #224, #225); the decisions are D-1 to D-14 in `design.md`.

- `InUse` carries the refused roots, the first root's `(referrer, class, slot)` rows,
  `more_count`, `hidden_count` and `filtered`. The outline's `InUse(referrers, hidden_count)` is
  its core.
- The 409 fails closed (D-10): an `InUse` that no `readable` callable filtered is answered with
  `referrers: []` and every referrer counted in `hidden_count`. This holds for every route,
  including the application's own. In-process callers keep the full names.
- An add in the same commit that links to a removed refusing root is refused before anything is
  sent. Like the guard, the check judges every `rdf:type` of the linking root and skips dependent
  records (D-9, D-12).
- A collection's link to a member is its `has_part` slot (D-8). A cascade refuses as a whole
  when a member is referenced from outside it.
- Out of scope, filed: #226 (a comment added in the commit that removes its target), #227
  (tidy-ups under the delivery floor).
