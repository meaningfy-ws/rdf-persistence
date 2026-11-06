<!-- Parents: openspec/specs/rp-aggregate-store ("Stale writes are refused"); architecture v1,
     docs/modules/ROOT/pages/architecture/index.adoc (building blocks: "Unique keys across
     aggregates", deferred). Seeds: inputs/seed.md. -->

# EPIC: Unique keys across aggregates, enforced at commit

> Candidate EPIC, shaped 2026-11-06 from the v1 future list. Not planned: the PLAN (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.

**Golden-thread parent:** capability `rp-aggregate-store` (requirement "Stale writes are refused")
and the deferred building block "Unique keys across aggregates" of
`docs/modules/ROOT/pages/architecture/index.adoc`.

## Appetite

**MEDIUM.** One new capability, a uniqueness guard in the commit, with its generator support, tests
and docs. The session and the generators are touched; the store port is not, unless the guard needs it.

## Why

v1 enforces `unique_keys` only inside one aggregate: the generated Pydantic validators
(`generation/extensions/pydantic_validators.py`) and the SHACL SPARQL constraint
(`generation/extensions/shacl_constraints.py`) refuse two owned items with equal keys in one
multivalued slot. Nothing compares two aggregates. The commit guard (`services/session.py`) is an
`ASK` on one graph's version token (PD-5), so two sessions creating two books with the same key both
commit. The architecture lists this as deferred: "two simultaneous writes can both pass".

## Solution outline

A schema declares that a slot, or a set of slots, is unique across the aggregates of one type in a
tenant. Every write path (the generic router and the unit of work) refuses a commit that would
break the key, inside the same guarded update, so that of two concurrent writes with the same key
exactly one succeeds. The refusal reaches the client as a problem response it can act on.

## Key decisions

- **DEC-1**: The declaration lives in the LinkML schema, and every artefact that restates it
  (validators, shapes, any key index template) is generated, by stock or toolkit-extended
  generators. Source: D-13; PD-24, PD-25; AGENTS.md, Project specifics.
- **DEC-2**: Optimistic concurrency stays as in v1: a fresh random version token per commit and a
  guarded update confirmed by an `ASK` (PD-5, `rp-aggregate-store`). The key guard joins that
  update; it does not replace it.
- **DEC-3**: SPARQL is built only through `domain/sparql.py` (PD-3).
- **DEC-4**: Each tenant has its own database (PD-6a, `rp-tenancy`), so no key can be checked across
  tenants in one update.

## Rabbit-holes

- **Atomicity of a multi-operation update.** The guard relies on Fuseki applying one SPARQL update
  request (operations joined by `;`) atomically. A second store may not (see `second-store`).
- **Key normalisation.** Case, whitespace and language tags make "equal" a choice.
- **Absent values.** v1's validators treat two absent values as equal inside an aggregate; across
  aggregates that would allow only one aggregate without the key.
- **Edits that change a key.** A replace that moves an aggregate to a key another holds must fail,
  and a replace that keeps its own key must not fail against itself.

## No-gos

- Uniqueness across tenants or across aggregate types.
- Uniqueness of owned parts across aggregates.
- A general constraint language or LinkML `rules` beyond unique keys.
- Changing v1's in-aggregate `unique_keys` behaviour.
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/services/session.py`: the guarded update also checks the declared keys.
- `rdf_persistence/generation/`: whatever the declaration needs to be read or generated.
- `rdf_persistence/entrypoints/problems.py`: a problem response for a key conflict.
- `docs/modules/ROOT/pages/architecture/`: the building block moves from deferred to v1.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-aggregate-store`: adds the cross-aggregate key guard (ADDED requirement).

## Impact

- Commits of keyed types write or read more in the guarded update; the cost is measured.
- A new problem type in the OpenAPI document (`entrypoints/openapi.py`).
