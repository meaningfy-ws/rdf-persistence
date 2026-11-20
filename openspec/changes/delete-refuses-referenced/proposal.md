<!-- Parents: issue #201 (inputs/seed.md); openspec/specs/rp-reverse-references, rp-service-api,
     rp-aggregate-store. Serves: MWB2 v2-03-project-and-resources task 7.1 (D-12).
     Seeds: inputs/seed.md. Consumer triage in ../uml-to-linkml/inputs/qa.md. -->

# EPIC: Refuse deleting an aggregate others point to (opt-in)

## Appetite

**SMALL.** One annotation and one check in the existing delete paths. `referrers` already exists and
is reused as is.

## Why

The generic delete removes an aggregate even when others reference it. Today the only way to refuse
is to take over every write of the class (`rp_writes: service`) and rewrite its routes. The
consumer's delete guard on collections needs this before `v2-03`'s last stage.

## Solution outline

A class annotation `rp_on_referenced_delete: refuse` (absent means today's behaviour). Both the
generic `DELETE /{type}/{id}` and `session.remove` then call `referrers` inside the transaction. If
any exist, they raise `InUse(referrers, hidden_count)`, which the API answers as `409` problem
`in-use`. The problem names the readable referrers (type, IRI, slot; capped, with a count of the
rest) and the count of unreadable ones. Nothing is deleted.

## Key decisions

- **DEC-1:** opt-in per class through an annotation in the metamodel's annotation enum, so the UML
  converter carries it with no change (`uml-to-linkml` DEC-2). Rejected: on for everyone, which
  would change today's behaviour.
- **DEC-2:** the check runs in the delete's transaction, so a referrer added concurrently is either
  seen or blocked by the same guarded update. Rejected: a pre-check outside it, which races.
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
