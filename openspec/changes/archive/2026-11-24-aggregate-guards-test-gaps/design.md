# Design: aggregate-guards-test-gaps

> Derives from: EPIC `aggregate-guards-test-gaps` (`proposal.md`). DEC-1 and DEC-2 are cited, not
> restated. The findings are those of `archive/2026-11-24-aggregate-guards/design.md` D-11, D-14.

## Tests

| TC | Finding | Case | Pins |
|---|---|---|---|
| TC-1 | R1-W2 | A rule reads shelf S, the same unit of work replaces S, a later read gives the replaced value | the cache `pop` in `Transaction.replace` |
| TC-2 | R1-W3 | Add, remove, add one IRI in one transaction: `aggregate` gives the re-added model, `classes_of` its classes | `_removed.discard` in add and replace |
| TC-3 | R1-W4, E5 | `aggregate` of a collected IRI whose types name no single root class gives None | `_decoded`'s `model_class` None |
| TC-4 | R1-W4, E8 | A rule reads B, the unit of work then removes B: the commit holds both changes | DEC-3 (no re-check) |
| TC-5 | R1-W5 | T4 rewritten: a spy on `session.get_graph` shows no store read, instead of `t._relied` | behaviour, not private state |
| TC-6 | R2-W4 | Tenant deletion with a delete rule registered on a root: no rule is called | DEC-5 (toolkit classes take no key) |
| TC-7 | R2-W5, E13 | `delete_cascade` of a collection whose member's rule refuses: 409 `refused` naming the member, nothing removed | the cascade's `Transaction.remove` |
| TC-8 | R2-W5 | A unit of work removing a root whose rule refuses: the commit is refused, nothing removed | `mapper.py` unit-of-work remove |
| TC-9 | R2-W5, E18 | Removing a commented root whose comment records' class has no rule: no rule runs for them, the root's rule runs once | D-8 |
| TC-10 | R2-S2 | A stale `If-Match` and a reader's plain `Conflict` inside a delete rule: the version conflict | DEC-2 |

## Docs

R1-S7: `user-manual/access.adoc`, the reader section: a missing aggregate is not cached, so each
rule that asks reads the store again, and its absence is not relied on, so an aggregate created
by another writer before the commit does not fail it.

## Verification

Each TC fails first (DEC-1), then passes; `make test-fast check-quality`; the lead's
`make check-all` and `make test-containers`.
