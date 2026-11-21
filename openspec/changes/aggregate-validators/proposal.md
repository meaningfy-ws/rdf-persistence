<!-- Parents: issue #240 (inputs/seed.md); openspec/specs/rp-service-api ("A consumer enforces its
     own rules on tenant writes", which this extends from the tenant root to every root).
     Serves: MWB2 v2-02-model-from-ea, phase B, task "check the package's 0..1 collection limits as
     package rules" (D-12). Seeds: inputs/seed.md, inputs/qa.md (owner's round of 2026-11-21). -->

# EPIC: Consumer validators on the writes of any aggregate root

## Appetite

**SMALL.** One keyword on `install_service` and the kit, run as one more step of the existing write
guard, plus a narrow read-only reader. The `root_validators` pattern is reused as is.

## Why

A consumer's rule that the schema cannot state (a limit per kind on a merged slot, a cross-slot
limit) can run today on the tenant root only. On any other root it has nowhere to run on the generic
API's writes, short of writing its own routes. The first consumer's `0..1`-per-kind collection limit
waits for this (the converter keeps the toolkit's multivalued `has_part`, so the limit is lost from
the schema).

## Solution outline

`install_service(..., aggregate_validators={"Shelf": [rule, ...]})` (and `ServiceKit`) maps a schema
class name to the rules for its roots, the roots of its subclasses included. Each rule is called with
`(old, new, principal, reader)`: the stored model or `None` on create, the model about to be
written, the principal, and a read-only reader. A rule may be a plain function or a coroutine
function. It refuses by raising `InvalidBody`, which is answered `422` before anything is written.
The rules run inside the write guard, so every guarded write of such a root runs them: the generic
POST and PUT, a UnitOfWork commit, a message-bus handler, a workflow transition. Start-up refuses a
class name that is not a root or a parent of a root, naming it. With no validators nothing changes.

## Key decisions

- **DEC-1:** one signature, `(old, new, principal, reader)`, sync or async; the toolkit awaits an
  awaitable result. Source: owner, Q-1. Rejected: two forms told apart by arity; async only (breaks
  the issue's sync example).
- **DEC-2:** the reader gives only the **classes** of a referenced aggregate, **access-checked**: an
  aggregate the writer may not read answers as unknown, so a rule learns nothing the writer could
  not. Source: owner, Q-2. Rejected: unchecked classes (leaks the class of a hidden aggregate); the
  whole aggregate (one graph read per reference, leaks more).
- **DEC-3:** the rules run in the kit's write guard, so they cover every guarded write of a root.
  Restore, migrations and the start-up sweep write quads directly and do not run them. Source: owner,
  Q-3. Rejected: the generic API only (a UnitOfWork could store what the rule refuses); restore too
  (a dump valid when taken could fail to restore).
- **DEC-4:** the failure contract is `root_validators`'s: `InvalidBody` and `ValidationError` give
  422; any other exception becomes a `RuntimeError` naming the rule; a non-`None` result is a
  `TypeError`. No timeout. Source: owner, Q-4 (risk accepted: a broken rule blocks every write of its
  class).
- **DEC-5:** the issue's PATCH acceptance is proved with PUT: the generic API has no PATCH route,
  and adding one is out of this EPIC. Source: planner (no PATCH route exists), owner may overrule.

## Rabbit-holes

- **Who the reader answers for.** An access check needs the caller's token roles and the tenant's
  access record, which a session does not hold (it holds a `Principal`, an IRI). The PLAN must say
  how the generic API hands the caller's read check to the session, and what a write with no caller
  behind it (a bus handler, the consumer's own UnitOfWork) reads.
- **Models from triples inside the guard.** The guard sees triples; the rules want models. Decoding
  must reuse the mapper and the generated classes, not a second decoder, and must not run when no
  rule applies (no cost for consumers without validators).
- **The tenant root.** It keeps `root_validators`. A name in `aggregate_validators` that is the
  tenant root's class also runs, in the guard; the PLAN states the order and that both run.

## No-gos

- No PATCH route.
- No validators on restore, migrations or the sweep.
- No change to `root_validators` or `grant_validators`, and no deprecation of them.
- No timeout, retry or ordering setting for rules; no rules on delete.
- No reader method beyond the classes of an aggregate.

---

## What Changes

- `install_service` and `ServiceKit`: keyword `aggregate_validators`.
- A public `AggregateValidator` type and a read-only `AggregateReader` (the classes of an aggregate,
  access-checked), exported beside `RootValidator`.
- The kit's write guard runs the rules for the root being written; start-up checks the class names.
- The generic API's writes hand the caller's read check to the session they open.
- Docs: the how-to on consumer rules; the public API partial.

## Capabilities

### Modified Capabilities

- `rp-service-api`: a consumer enforces its own rules on the writes of any root, not only the
  tenant root.

## Impact

`api/entrypoints` (`service.py`, `kit.py`, the router's write calls), `api/services/aggregates.py`,
`collaboration/services/write_guards.py`, the session's opening (`persistence/services/session.py`,
`tenancy/services/tenancy.py`), the public surface (`__init__.py`, `tests/fixtures/public-surface.json`).
Not breaking: the keyword is optional.

## Delivery reconciliation

One stage, one PR. What was built against what this EPIC promised (P-0004):

| Promise | Built | State |
|---|---|---|
| `aggregate_validators` on `install_service` and `ServiceKit` | `api/entrypoints/service.py`, `kit.py` | delivered |
| `AggregateValidator`, `AggregateReader` exported beside `RootValidator` | `rdf_persistence/__init__.py`, public-surface fixture, reference partial | delivered |
| Rules run in the write guard on every guarded add and replace; start-up checks the names | `collaboration/services/aggregate_validators.py`, `write_guards.py` | delivered |
| The generic API's writes hand the caller's read check to the session | `Session.may_read`; router create/replace/tenant-root PUT, rename, `kit.collaboration` | delivered |
| Docs: how-to on consumer rules; public API partial | `user-manual/access.adoc#aggregate-validators`, `architecture/data-flows.adoc`, `questions.adoc` | delivered |
| DEC-5: PATCH acceptance proved with PUT | A-2 (refused replace) | delivered as decided |

Deviations: none from DEC-1 to DEC-5; delivery decisions D-1 to D-6 in `design.md`.
