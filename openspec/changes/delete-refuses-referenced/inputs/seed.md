<!-- Secondary input, never groomed: GitHub issue #201 (meaningfy-ws/rdf-persistence), fetched 2026-11-20. The EPIC (../proposal.md) supersedes it. -->

# #201 Refuse the generic delete of an aggregate that others point to (opt-in)

## Summary
Let a class opt in to having the generic delete refuse an aggregate that other aggregates point to.

## Context
Consumer: MWB2, change `v2-03-project-and-resources` (task 7.1, PLAN DEC-2/DEC-18); toolkit locked at `c671fefb` (v0.7.0).

## Current behaviour
The generic `DELETE /{type}/{id}` and kit-session removes delete an aggregate even when other aggregates reference it. `Collaboration.referrers` reports referrers but nothing blocks the delete. The documented way to refuse is to take over all writes of the class (`rp_writes: service`) and re-implement its routes, which is the toolkit's job.

## Expected behaviour / proposed capability
A class annotation, e.g. `rp_on_referenced_delete: refuse` (default: today's behaviour). With it, the generic delete and session removes call `referrers` inside the transaction and, when any exist, answer `409` problem `in-use`, naming the readable referrers (type, IRI, slot; capped, with a count of the rest) and `hidden_count`; nothing is deleted.

```yaml
classes:
  Author:
    annotations:
      rp_on_referenced_delete: refuse
```

```python
await session.remove(author)  # raises InUse(referrers=[...], hidden_count=0) when a Book points to it
```

## Why it belongs in rdf-persistence
Referential safety on delete is generic to any model-driven RDF application; the toolkit already owns `referrers` and the generic routes.

## Acceptance
- Given `Author` annotated `refuse` and a `Book` referring to it, When a caller deletes the author, Then 409 `in-use` naming the book, and the author remains.
- Given the only referrer is unreadable to the caller, When deleting, Then 409 with `hidden_count: 1` and no name.
- Given no referrer, When deleting, Then 204.
- Given a class without the annotation, Then behaviour is unchanged.

## Impact on the consumer
Without it, MWB2 must either let referenced resources and collections be deleted or rewrite their write routes; the task waits.


## Comments

