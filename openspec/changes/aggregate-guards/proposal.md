<!-- Parents: issues #305, #309 (inputs/seed.md); openspec/specs/rp-service-api, requirement
     "A consumer enforces its own rules on the writes of any root" (archived change
     2026-11-21-aggregate-validators, #240). Q&A: inputs/qa.md (2026-11-24).
     Serves (D-12): MWB2 v2-07-package-editor DEC-2 / P-4 (#305: a package's source range checked
     on the API, not only in the Web App); v2-06-conceptual-mapping T-2 (#309: no delete of a CM
     under review through the generic route). -->

# EPIC: Aggregate guards: rules that read referenced aggregates, and rules on delete

## Appetite

**SMALL**, in two stages, one PR each: #305, then #309. One capability (the consumer's aggregate
rules) is touched in a few places: the reader, the write guard and the transaction's remove.
The existing structure is reused.

## Why

- **#305.** A consumer rule on a root can ask the reader only which classes an aggregate it names
  has. A rule like "a package's minimum source version ≤ its maximum" must compare values held by
  two other roots, and today it cannot see them. The consumer checks the rule in its Web App only,
  so a request sent straight to the API can store a reversed range.
- **#309.** Rules run on add and replace, never on delete. "A conceptual mapping under review may
  not be deleted" has nowhere to run, so the generic `DELETE` skips it.

## Solution outline

- **The reader hands over a referenced aggregate.** `await reader.aggregate(iri)` gives the
  aggregate as its generated model, as this transaction leaves it, or None when it is missing,
  removed in this transaction, or not readable by the writer. Reading a stored aggregate also
  makes the commit depend on its version: if it changes before the commit, the commit fails as a
  conflict, so a rule never passes on stale data.
- **Delete rules.** The kit takes `delete_validators`: a mapping from a class to rules called as
  `(old, principal, reader)`. They are keyed and checked like `aggregate_validators`, and run on
  every transaction remove of a root of that class or a derived class, before anything is
  written. A rule refuses with `Conflict`, which the generic route answers with 409 and the
  rule's message. A refusal stops the whole transaction, a cascade included.

## Key decisions

- **DEC-1:** `AggregateReader.aggregate(iri) -> BaseModel | None`, decoded with the class the
  validators already pick for a root (`model_class`). Rejected: `values(iri, slot)` and
  `get(iri, slots=…)`, which hand over untyped values (PD-24: data goes through the generated
  models).
- **DEC-2:** a stored aggregate read through `aggregate()` is relied on at the version read
  (`GuardContext.rely_on`). An aggregate taken from this transaction's collected triples is not,
  since the transaction itself holds it. Rejected: accepting the race.
- **DEC-3:** `aggregate()` answers as the transaction stands when it is called. It returns what an
  earlier add or replace collected, and None for an earlier remove. A remove of B after A's rule
  has read B is not re-checked (RISK-5).
- **DEC-4:** delete rules are a separate registry, `delete_validators`, so the signature of
  existing rules does not change. Same key check (`_check_key`), same class-chain selection, same
  error contract, except that the refusing exception is `Conflict` (409). `InvalidBody` from a
  delete rule is a bug in the rule (`RuntimeError`). Rejected: running the write rules with
  `new=None`, which breaks every existing rule.
- **DEC-5:** delete rules run on every `Transaction.remove` of a root whose class chain has rules:
  the generic route, a unit of work, a collection's cascade and file removal. Restore and
  migrations open no session, so they run none. The system database's access records are toolkit
  classes, which no key can name. Comment records dropped with their resource are not a remove.
  Dropping a tenant's database is not one either.
- **DEC-6:** one decode per IRI per transaction. The reader caches what `aggregate()` decoded,
  keyed by IRI, and drops an entry when the transaction collects a change to that IRI (RISK-4).
- **DEC-7:** two stages, two PRs into `develop`: #305, then #309. #309's rules take the same
  reader, so the reader comes first. This EPIC lands with stage 1's PR.

## Rabbit-holes

- `GuardContext.collected` holds adds and replaces only ("a remove adds nothing"). DEC-3 needs the
  transaction's removals too: `GuardContext` gains them.
- A rule that reads A itself (the root being written) gets the stored A, not the new one: the new
  one is the rule's `new` argument. Document it; don't special-case it.
- A cascade's delete rules run inside the cascade's transaction. A part's refusal surfaces as the
  parent's 409 with the part's message, so the message must name the root it refuses (RISK-2).
- `Session.remove` and `Transaction.remove` take no principal beyond the session's own; the rule's
  `principal` is `session.principal`, as for write rules.

## No-gos

- No rerunning of A's rules when B changes. The consumer registers the symmetric rule on B (RISK-3).
- No query API on the reader (no listings, no `find`); one aggregate by IRI only.
- No change to the write rules' signature or their 422.
- No delete rules on tenant deletion, restore or migrations.
- No consumer-defined HTTP status: `Conflict` is the only refusal.

---

## What Changes

- `AggregateReader.aggregate(iri)`, with a version guard and a per-transaction cache.
- `GuardContext` carries the transaction's removals.
- The `WriteGuard` port gains `prepare_remove`. `Transaction.remove` calls it before collecting.
- `ServiceKit` and `install_service` take `delete_validators`, and `DeleteValidator` is exported
  from the top level.
- Docs: `user-manual/access.adoc` (rules section), `architecture/data-flows.adoc`, `questions.adoc`
  (the new question "How do I refuse a delete?").

## Capabilities

### Modified Capabilities

- `rp-service-api`: a rule reads a referenced aggregate; a consumer refuses deletes.

## Impact

`collaboration/services/aggregate_validators.py`, `collaboration/services/write_guards.py`,
`persistence/services/session.py` (port, context, remove), `api/entrypoints/kit.py`, the top
package's exports, three docs pages. There are no breaking changes: the reader gains a method,
and the kit gains an optional argument. Once the consumer refreshes its lock, it moves its
range check and its CM delete check into rules.
