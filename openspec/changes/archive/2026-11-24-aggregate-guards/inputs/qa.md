# Q&A record (secondary, never groomed): shaping session 2026-11-24

Seeds: issues #305 and #309 (`seed.md`). The backlog slice that places them is the owner's round 1
of `consumer-gap-fixes/inputs/qa.md`: by concern, this change holding #305 and #309.

Code read on `develop` at `f9f6fa74`:

- `collaboration/services/aggregate_validators.py` (`AggregateReader`, `_Reader`,
  `run_aggregate_validators`, `_check_key`)
- `collaboration/services/write_guards.py` (`WriteGuards.prepare`, `_run_aggregate_validators`,
  `_decoded_stored`)
- `persistence/services/session.py` (`GuardContext`, `WriteGuard`, `Session.remove`,
  `Transaction.remove`, `_context`, `_rely_on`)
- the callers of `transaction.remove`: `mapper.py` l.490 (unit of work),
  `reference_collections.py` l.265-269, `aggregates.py` l.163, `file_removal.py` l.51,
  `tenancy.py` l.931
- `api/entrypoints/kit.py` (`aggregate_validators`), `problems.py` (`Conflict` → 409)
- `openspec/specs/rp-service-api` ("A consumer enforces its own rules on the writes of any root")

## Round 1

| Question | Answer |
|---|---|
| #305: what does the reader give about a referenced B? | **`aggregate(iri)`**: B decoded as its generated model, or None. |
| #305: B changes before A's write commits | **Rely on B's version**: the commit fails if B changed. |
| #309: how is a delete refused? | **Separate delete rules**, `delete_validators={Class: [rule(old, principal, reader)]}`. Existing rules are untouched. |
| #309: which removals run them? | **Every transaction remove** of a root of the class, cascades included. Dropping a tenant's database is excluded. |

## Round 2

| Question | Answer |
|---|---|
| How does a delete rule refuse? | **`Conflict`, 409**. |
| Risks to treat | All four: a hot B causes 409s; a cascade is blocked by a part's rule; inverse edits are not rerun; decode cost. |
| Edge scenarios | All four: B in the same transaction; B removed in the same transaction; a delete in a cascade; an unreadable B. |
