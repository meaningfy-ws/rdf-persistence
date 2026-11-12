<!-- Parents: openspec/specs/rp-aggregate-store ("Stale writes are refused"); architecture v1,
     docs/modules/ROOT/pages/architecture/index.adoc (building blocks: "Unique keys across
     aggregates", deferred). Depends on: change atomic-commit (issue #83). Seeds: inputs/seed.md. -->

# EPIC: Unique keys across aggregates, enforced at commit

> Candidate EPIC, shaped 2026-11-06 from the v1 future list; re-shaped and planned 2026-11-12
> (see "Re-shaped 2026-11-12" below). The PLAN is design.md + tasks.md. Starts after
> `atomic-commit` is merged.

**Golden-thread parent:** capability `rp-aggregate-store` (requirement "Stale writes are refused")
and the deferred building block "Unique keys across aggregates" of
`docs/modules/ROOT/pages/architecture/index.adoc`.

## Appetite

**MEDIUM.** One new capability, a uniqueness guard in the commit, with its declaration checks,
tests and docs. The session's transaction (from `atomic-commit`) and the hard check are touched;
the store port is not.

## Why

v1 enforces `unique_keys` only inside one aggregate: the generated Pydantic validators
(`generation/extensions/pydantic_validators.py`) and the SHACL SPARQL constraint
(`generation/extensions/shacl_constraints.py`) refuse two owned items with equal keys in one
multivalued slot. Nothing compares two aggregates. The commit guard (`services/session.py`) is an
`ASK` on one graph's version token (PD-5), so two sessions creating two books with the same key both
commit. The architecture lists this as deferred: "two simultaneous writes can both pass".

## Solution outline

A schema declares, on an aggregate root, a LinkML `unique_keys` entry annotated
`rp_unique_scope: tenant`: the key's slots are unique across the aggregates of that type in a
tenant. Every write path (the generic router and the unit of work) goes through the session's
transaction (`atomic-commit`); the transaction adds one guard per claimed key value to its single
guard operation, so that of two concurrent writes with the same key exactly one succeeds. Two
changes of one transaction claiming the same value are refused before anything is sent. The
refusal is a `KeyConflict` (a `Conflict`), and reaches the client as a 409 problem of its own type.
Existing duplicates are listed by an operator report, not by generation.

## Key decisions

- **DEC-1**: The declaration lives in the LinkML schema: `unique_keys` on the aggregate root with
  the annotation `rp_unique_scope: tenant` (developer, 2026-11-06). The runtime reads it from the
  `SchemaView`, as the mapper and listings do; no artefact restates it. Source: D-13; PD-24,
  PD-25; AGENTS.md, Project specifics.
- **DEC-2**: Optimistic concurrency stays as `atomic-commit` makes it: one update request per
  commit, one guard operation holding every guard, a fresh version token per root, an `ASK` to
  confirm. The key guards join that guard operation; they do not replace it.
- **DEC-3**: SPARQL is built only through `domain/sparql.py` (PD-3).
- **DEC-4**: Each tenant has its own database (PD-6a, `rp-tenancy`), so no key can be checked across
  tenants in one update; the scope is per tenant and per type (developer, 2026-11-06).
- **DEC-5** (developer, 2026-11-06): exact match of RDF terms; an aggregate with any key slot
  absent claims nothing and never conflicts; a clash is 409 Conflict with its own problem type.
- **DEC-6** (re-shaped 2026-11-12): existing duplicates are reported by an operator check on a
  tenant (`Session.key_duplicates()`), not by generation, which never sees stored data.

## Rabbit-holes

- **Atomicity of a multi-operation update.** The guard relies on Fuseki applying one SPARQL update
  request (operations joined by `;`) atomically, as `atomic-commit` does. A second store may not
  (see `second-store`).
- **The cost of the guard.** Each claimed key value adds one `FILTER NOT EXISTS` to the guard
  operation: a lookup of the value across the tenant's aggregate graphs, on every commit of a keyed
  type. With the value bound, Fuseki's quad index finds it without scanning the tenant, if the
  pattern on the value is evaluated first; the PLAN measures it on Fuseki (1,000 books).
- **Key normalisation.** Case, whitespace and language tags make "equal" a choice; exact match was
  chosen (DEC-5).
- **Absent values.** v1's validators treat two absent values as equal inside an aggregate; across
  aggregates that would allow only one aggregate without the key, so absent never conflicts.
- **Edits that change a key.** A replace that moves an aggregate to a key another holds must fail,
  and a replace that keeps its own key must not fail against itself.
- **Existing duplicates.** Declaring a key over data that already repeats it makes those
  aggregates unwritable until their key changes; the operator report finds them first.

## No-gos

- Uniqueness across tenants or across aggregate types (a subclass is its own type).
- Uniqueness of owned parts across aggregates.
- A general constraint language or LinkML `rules` beyond unique keys.
- Changing v1's in-aggregate `unique_keys` behaviour.
- Normalising key values (case, whitespace, language).
- Refusing or repairing existing duplicates automatically, at generation or at start-up.
- Any consumer term, model or code.

## Re-shaped 2026-11-12

Logged edits, made when the PLAN was derived (leader; the developer may overrule):

- **Depends on `atomic-commit`** (issue #83) instead of being "contained in the commit's own
  update": that change replaces the per-aggregate guarded updates with one transaction whose
  guard operation takes extra guard patterns (its DEC-6). The key guard is such a pattern.
- Q-1 and Q-3 to Q-7 of `inputs/seed.md` resolved as the developer accepted on 2026-11-06,
  written as DEC-1, DEC-4, DEC-5.
- **Q-7 changed in substance**: "generation reports existing duplicates" is impossible, since
  generation reads schema files and never connects to a store. It becomes an operator report
  (DEC-6); a start-up check was rejected (it would scan every tenant on each start and could only
  warn or take the service down for a data problem).
- Rabbit-hole on the cost of the guard added; two No-gos added (normalisation, automatic repair).

---

## What Changes

- `rdf_persistence/model/rp_core.yaml`: the `rp_unique_scope` annotation, its `UniqueScope`
  values, and the `AggregateKey` and `KeyDuplicate` classes (regenerated).
- `rdf_persistence/generation/checks/hard.py`: a scoped key is checked (where it is declared, its
  slots, its scope).
- `rdf_persistence/services/unique_keys.py` (new): the keys of a schema, the claims of a change,
  the guard and diagnosis queries.
- The session's transaction (`services/session.py`, from `atomic-commit`): adds the key guards,
  refuses duplicate claims, diagnoses a key clash; `Session.key_duplicates()`.
- `rdf_persistence/domain/exceptions.py`, `entrypoints/problems.py`, `model/service/rp_service.yaml`:
  `KeyConflict` and its 409 problem type.
- `docs/modules/ROOT/pages/`: the building block moves from deferred to delivered; the adoption
  how-to shows the declaration and the report.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-aggregate-store`: adds the cross-aggregate key guard and the duplicates report (ADDED).
- `rp-generation`: adds the checks of a scoped key declaration (ADDED).
- `rp-service-api`: adds the key-conflict problem (ADDED).

## Impact

- Commits of keyed types carry one more pattern per claimed value in the guard operation; the cost
  is measured on Fuseki.
- A new problem type in the OpenAPI document (`entrypoints/openapi.py`).
- Public API: `KeyConflict`, `Session.key_duplicates` and the `KeyDuplicate` it returns. Nothing
  removed.
