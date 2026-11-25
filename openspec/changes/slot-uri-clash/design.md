# Design: slot-uri-clash

> Derives from: EPIC `slot-uri-clash` (proposal.md, DEC-1 to DEC-4). Facts and the probe:
> `inputs/seed.md`; the owner's answers: `inputs/qa.md`.

## Context

`hard_problems(view, folder)` (`rdf_persistence_generation/checks/hard.py`) runs once per target
and already holds #278's `_slot_name_problems`, which compares slot *names* across the toolkit and
the application. This rule compares *IRIs* of different names. `slot_iri(view, schema, slot)`
(`rdf_persistence/schema/services/schema.py`) gives a slot's expanded IRI as its own module defines
it; it is reused, not copied (P-0008).

## Decisions

- **PD-1 What is compared.** For each schema of `view.schema_map` (after `view.imports_closure()`):
  every slot of `schema.slots` and every attribute of every class of `schema.classes`, as the
  triple (IRI, name, module name), the IRI from `slot_iri(view, schema, slot)` (an attribute is a
  `SlotDefinition` too). Slots and attributes with `identifier: true` are skipped (DEC-2).
- **PD-2 What clashes.** Group the triples by IRI; an IRI with two or more *distinct names* is a
  clash. One name declared twice (a slot and an attribute of the same name, or #278's same-name
  case) counts once, so this rule never repeats #278's.
- **PD-3 Who reports it.** A clash is reported by a target only when one of its triples comes from
  the target's own schemas (the names `hard_problems` already passes as `own`) (DEC-4). The
  toolkit's targets check the toolkit's own pairs; a consumer target does not report them again.
- **PD-4 The problem.** One `CheckProblem` per clashing IRI, rule `HardRule.SLOT_IRI` (new value
  `slot_iri` in `rp_generation.yaml`'s `HardRule`, with `title`, `description` and `meaning` like
  its neighbours; `make generate`), element: the first name, in sorted order, of the slots declared
  in the target's own schemas; message:
  `the slots <a> of <module>, <b> of <module> resolve to <iri>: reuse one slot, or give the other its own slot_uri`,
  every name on the IRI listed (two or more), joined by ", " and sorted by name. Order of
  problems: sorted by IRI (reproducible output).
- **PD-5 Placement.** A function `_slot_iri_problems(view, own)` in `checks/hard.py`, called from
  `hard_problems` next to `_slot_name_problems`. No new module.

## Algorithm / approach

Worked example (the #206 case): `books.yaml` (own) declares `parts` with `slot_uri:
dcterms:hasPart`; `rp_collections` (toolkit) declares `has_part` on `dcterms:hasPart`. Triples:
(`http://purl.org/dc/terms/hasPart`, `parts`, `books`), (same IRI, `has_part`, `rp_collections`).
Two names, one own → one problem, element `parts`:
`the slots has_part of rp_collections, parts of books resolve to http://purl.org/dc/terms/hasPart: ...`.

Exempt example: `rp_core.id` (`identifier: true`) is skipped; `templates.identifier` alone on
`dcterms:identifier` is no clash.

## Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Compare `view.all_slots()` | Walk `schema_map` module by module | The merged view keeps one slot per name and resolves IRIs against the root's prefixes, hiding the module that declared it |
| Exempt `dcterms:identifier` by IRI | Skip `identifier: true` | DEC-2 |
| Re-implement IRI expansion | `slot_iri` | P-0008; it is the expansion #278 uses |

## Error matrix

| Failure mode | Detection | Handling |
|---|---|---|
| Two own slots on one IRI | PD-2 | `slot_iri` problem, exit 1, nothing written (the hard step precedes writing) |
| An own slot on a toolkit slot's IRI | PD-2, PD-3 | as above, element the own slot |
| Two toolkit slots on one IRI | the toolkit target's own run | reported once by that target; consumer targets silent (PD-3) |
| A slot without `slot_uri` whose default IRI equals another's `slot_uri` | `slot_iri` expands `<default_prefix>:<name>` | as above |
| A module with no `default_prefix` and a slot without `slot_uri` | `slot_iri` would expand `None:<name>` | already a hard problem (`HardRule.IRI`, "a default prefix"); this rule may also see a junk IRI, which cannot equal a real one, so no false clash |
| An identifier slot beside a plain slot on its IRI | PD-1 skips it | no problem (the library fixture, the converter's golden output) |
| `slot_usage` gives one class another `slot_uri` | not read (Rabbit-holes) | not compared; accepted |

## Risks / Trade-offs

- **RISK-1 A consumer model with a clash stops generating.** Likelihood: low (the probe: none in
  the consumer's model). Impact: generation fails until a slot is reused or renamed. Accepted
  (owner, 2026-11-25), with a `CHANGELOG.md` *BREAKING* entry (D-1) and a message that names the
  fix.
- **RISK-2 A false clash from prefix expansion** (two prefixes for one namespace written
  differently). `slot_iri` expands to full IRIs, so two CURIEs of one IRI compare equal, which is
  the intent; no false clash from spelling.
- **RISK-3 A test that builds its own schema trips the rule.** The probe covered the toolkit's 30
  schemas, the library fixture and both UML golden stages (no clash but the exempt pair); schemas
  written inline in tests were not probed. Likelihood: low; impact: a red test in the task gate.
  Handling: the builder lists each such test; an accidental clash in a test schema is fixed in the
  test (it would be wrong output in real use), a deliberate one goes to the lead.

## Tests

- `tests/generator/unit/test_hard_check.py`, the `FAULTS` table (run by
  `test_a_planted_fault_is_reported_with_its_rule_and_element`, CI job `test-generator`): three
  rows of `HardRule.SLOT_IRI`, each a fault planted in a copy of the library fixture (spec
  scenarios 1 and 3: the rule and the element).
- One test in the same file, on fault (a), through `rp-generate`: exit 1, the message holds both
  slots, both modules and the IRI, nothing is written (the rest of spec scenario 1).
- Negative cases, existing and unchanged: `test_the_toy_library_passes` (the library fixture holds
  `id` and `identifier` on `dcterms:identifier`: spec scenario 2) and
  `test_the_toolkits_own_schemas_pass` (no toolkit pair).
- No test moves or goes.

## Delivery decisions

- **D-1 (owner, 2026-11-25) The CHANGELOG entry is BREAKING.** It goes under `### ⚠ BREAKING` of
  `[Unreleased]`, the house style for a model that generated before and is now refused; this
  replaces the "Changed" of round 1 (RISK-1).
- **D-2 (owner, 2026-11-25) The PLAN is accepted at 8.85/10 with the gate's five gaps fixed**
  (`evidence/clarity-gate.md` run 2): fault anchors pinned, a full-message and writes-nothing test
  added, the `Fault` field names, deep links, and the CHANGELOG section (D-1).

## Open Questions

None.
