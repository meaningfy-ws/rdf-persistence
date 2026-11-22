# Q&A record: activity-iri-policy (secondary; never groomed)

Planned by a subagent that could not ask; the owner's round is open. The PLAN is complete under
each recommendation; the "PLAN assumes" column is what it does today.

## Round 1 (2026-11-22, open)

| Id | Question | Options and trade-offs | Recommended | PLAN assumes |
|---|---|---|---|---|
| OPEN-1 | Where is an activity's policy IRI minted? | (a) **placement at the commit**: commands keep a provisional `urn:uuid:<u>`, the session records `<template>(u)`; no API change, consumer opts in by settings; a handler's `command.id` differs from the stored IRI under a policy (RISK-2, RISK-3). (b) **tenant-aware minting**: `command()` and `new_activity_id()` take the tenant and `Iris`; ids agree everywhere, but the public `command(cls, **slots)` and every consumer handler change (breaking). | (a) | (a): DEC-2, PD-5, PD-6 |
| OPEN-5 | May a non-default activity template leave out the tenant (`{base}activity/{id}`)? | Allowing it: shorter IRIs, but a restore to a new tenant id leaves the activities as they were (they are not the tenant's portable data, against #197). Refusing it: every non-default template holds `{tenant}` or `{tenant_id}`; the default `urn:uuid:{id}` stays allowed. | refuse at settings validation | refuse: PD-1, PD-12 |

## Decided by the planner (after the reviewer's gate, 2026-11-22; formerly open)

- OPEN-2 (what `{id}` stands for) → PD-10: always the UUIDv4.
- OPEN-3 (the issue's `{base}{tenant}/…`) → PD-9: documented as `{tenant}/activity/{id}`;
  `{base}{tenant_id}/activity/{id}` also allowed.
- OPEN-4 (`urn:uuid:` as `Last-Event-ID` under a policy) → PD-11: reset, the store not asked.

Lead's decisions, not asked: DEC-4/PD-3 (movability and collision checks), DEC-5/PD-4 (the
default template reserves no word), commit markers unchanged (no-go).

## Question round parked (2026-11-22)

The owner parked the question round: the OPEN items above are unanswered. The PLAN stands
under the recommended answers; nothing is decided until the owner answers.
