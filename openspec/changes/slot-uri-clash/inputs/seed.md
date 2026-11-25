# Seed: slot-uri-clash (secondary; never groomed)

## Issue #206: generator: refuse two slots that share one slot_uri

> An application model can declare its own slot with the same `slot_uri` as a toolkit slot, for
> example `slot_uri: dcterms:hasPart` beside the toolkit's `has_part` slot. Two JSON-LD terms then
> map to one IRI, so compaction picks one of them, and on a collection class two slots would share
> the membership predicate.
>
> Proposal: `rp-generate` checks the combined schema (toolkit + application) and refuses, naming
> both slots, when two slots resolve to the same IRI.
>
> Context: follow-up of `collection-has-part` (#199), RISK-2.

## Where it was decided to shape it

`generator-module-cycles` (archived 2026-11-25) scoped #206 out (its DEC-5); the owner answered its
OPEN-1 on 2026-11-25: "its own TINY EPIC in the generator's checks, after this one, with identifier
slots exempt".

## Probe (lead, 2026-11-25)

Every slot and class attribute of each closure, grouped by its expanded IRI (the toolkit's
`load_schema`, so the import map resolves), the `identifier: true` ones marked:

| Schema | IRIs | Two or more slots on one IRI |
|---|---|---|
| the consumer's `models/mwb2.yaml` (its `HEAD` `558cc82`, read-only copy) | 160 | `dcterms:identifier`: `id` (identifier) and `identifier` |
| `tests/fixtures/library/library.yaml` | 108 | the same pair |
| `tests/generator/fixtures/uml/golden/stage2/library.yaml` | 55 | the same pair |

With `identifier: true` slots left out, no schema has a clash. (The earlier probe P-3 of
`generator-module-cycles` reported the library fixture clean; it has since gained `identifier`.)

## Code read

- `rdf_persistence_generation/checks/hard.py` `hard_problems`, `_slot_name_problems` (#278's
  sibling check: an application slot named like a carried toolkit slot).
- `rdf_persistence/schema/services/schema.py` `slot_iri` (the expanded IRI of a slot as its own
  module defines it), `slot_name_clashes`.
- `rdf_persistence_generation/model/rp_generation.yaml` `HardRule` (`toolkit_slot_name`).
- `tests/generator/unit/test_hard_check.py` (the `Fault` table: one fault applied to a copy of the
  library fixture per rule).
- `openspec/specs/rp-generation/spec.md` requirements "The identifier slot is never a property"
  and "An application slot does not take the name of a carried toolkit slot".
