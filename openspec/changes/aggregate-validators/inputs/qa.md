<!-- Secondary input, never groomed: the owner's answers to the shaping round, 2026-11-21.
     proposal.md (DEC-1 to DEC-5) and design.md carry them. -->

# Q&A: aggregate-validators, 2026-11-21

Facts read before the round (develop `4a22f06e`):

- `RootValidator` (`tenancy/services/tenancy.py`) is `(old, new, principal) -> None`, forced sync
  (`_plain` raises `TypeError` on a coroutine), and runs on the tenant root only (create, PUT,
  rename, restore).
- Every write of a root (generic POST and PUT, UnitOfWork commits, message-bus handlers, workflow
  transitions, comments, `Tenancy`'s own root writes) goes through `Transaction.add_graph` /
  `replace_graph`, which call the kit's one `WriteGuard` (`WriteGuards.prepare`, async, given the
  session). Restore (`import_quads`), migrations and the tenant sweep write quads directly and do
  not.
- The generic API has POST, PUT and DELETE; **there is no PATCH route**.
- `Session.heads(iris)` reads the classes of aggregates from the registry and checks no access.

| Id | Question | Owner's answer |
|---|---|---|
| Q-1 | Signature? | One form, `(old, new, principal, reader)`, sync or async; the result is awaited when awaitable. |
| Q-2 | What may the reader give? | The classes of a referenced aggregate, **access-checked**: an aggregate the writer may not read answers as unknown. (Not the recommended unchecked form.) |
| Q-3 | Which writes run the validators? | Every guarded write (the write guard). Restore and migrations are not covered. |
| Q-4 | Risk: a buggy or slow validator blocks every write of its class. | Accept, with root_validators' contract: `InvalidBody`/`ValidationError` → 422, any other exception → `RuntimeError` naming the validator, a non-`None` result → `TypeError`. No timeout. |

Planner's reading, not asked (recorded as decisions in proposal.md / design.md, the owner may
overrule): the issue's PATCH acceptance is tested as PUT (no PATCH route exists, and adding one is a
no-go); `root_validators` stays as it is; a write with no caller behind it (bus handler, UnitOfWork
in the consumer's own code) reads every class, as a session already does (design PD-4).
