<!-- Parents: issue #206; collection-has-part (#199) RISK-2; generator-module-cycles DEC-5 and the
     owner's answer to its OPEN-1 (2026-11-25). -->

# EPIC: rp-generate refuses two slots on one IRI

**Golden-thread parents:** issue #206; `rp-generation` requirements "The identifier slot is never
a property" and "An application slot does not take the name of a carried toolkit slot" (#278, the
sibling check on names); `openspec/changes/archive/2026-11-25-generator-module-cycles/` DEC-5 and
`inputs/qa.md` OPEN-1.

## Appetite

**TINY.** One rule added to the generator's hard check, beside #278's; no new concept.

## Why

A model can give two slots the same predicate IRI, for example its own slot on `dcterms:hasPart`
beside the toolkit's `has_part`. The JSON-LD context then maps two terms to one IRI, so compaction
keeps one of them, and on a collection class two slots would claim the membership predicate. The
generator accepts this today and writes an ambiguous context. The membership move of #199 made
the case likely; it was left out of that appetite.

## Solution outline

`rp-generate`'s hard check gains one rule: among the slots and class attributes of a target's
import closure (toolkit and application), two with different names on one expanded IRI are a
problem, unless one of them is an identifier slot. The problem names every slot on that IRI, the
module each comes from, the IRI, and the two fixes (reuse the existing slot, or give yours its own
`slot_uri`). Generation stops with exit 1 and writes nothing, like every hard problem. The models
in the repository and the consumer's current model pass unchanged (probe, `inputs/seed.md`).

## Key decisions

- **DEC-1:** a hard problem (exit 1), not a warning. Reason: the generated context and shapes are
  wrong, not merely unusual. Rejected: a soft check, or soft for one release then hard (two changes
  for a case the probe found nowhere).
- **DEC-2:** a slot or attribute with `identifier: true` is left out of the comparison. Reason: it
  is written as the node's IRI (`@id`) and never as a predicate ("The identifier slot is never a
  property"), so the toolkit's `id` beside a plain `identifier` on `dcterms:identifier` is no
  clash. Rejected: exempting the IRI `dcterms:identifier` by name (it would let two plain slots
  share it).
- **DEC-3:** all slots and class attributes of the import closure are compared, toolkit included,
  each by its expanded IRI as its own module defines it (`slot_iri`: the `slot_uri`, or the
  module's default prefix and the slot name). One slot name is one slot, wherever it is refined.
  Rejected: comparing application slots against the toolkit only (a toolkit pair would go unseen).
- **DEC-4:** the rule runs for every target, and a target reports a clash only when one of its
  slots is declared in the target's own modules. Reason: each clash is reported once, by the target
  that owns it; the context and shapes of every target are generated from the same closure.
  Rejected: stored domain targets only.

## Rabbit-holes

- A `slot_usage` that gives a slot another `slot_uri` on one class: not compared (the check reads
  slot definitions, not induced slots). No such override exists in the repository's models.
- A slot named like a toolkit slot under another IRI is #278's rule, not this one; the two must not
  report the same pair twice (one compares names, this one IRIs of different names).

## No-gos

- Changing the converter: its `identifier` attribute beside `id` is exempt by DEC-2.
- Any check on class IRIs (`class_uri`) or enum IRIs.
- A switch to turn the rule off.

---

## What Changes

- `rp-generate` refuses a target whose closure has two differently named slots or attributes on one
  expanded IRI, identifier slots aside (new hard rule `slot_iri`).
- **BREAKING** for a model that has two slots on one IRI: it is refused until a slot is reused or
  given its own IRI (none in the repository or the consumer's model today).
- Docs: the hard rules of `architecture/generation.adoc`; `CHANGELOG.md` *BREAKING* under
  `[Unreleased]` (RISK-1, design.md D-1).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rp-generation`: a requirement added, "Two slots do not share one IRI".

## Impact

- Code: `rdf_persistence_generation/checks/hard.py`, `rdf_persistence_generation/model/rp_generation.yaml`
  (`HardRule.slot_iri`) and its generated files; the `rp-manifest.json` files, only because
  `hard.py` is a generator input. Delivered in PR #376.
- Tests: `tests/generator/unit/test_hard_check.py`; one row in `tests/audit/scenario-map.csv`.
- Consumers: a model with two slots on one IRI stops generating until it reuses the slot or gives
  its own one another IRI (RISK-1); the consumer's current model has none.
