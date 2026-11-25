EPIC: slot-uri-clash (proposal.md). Decisions: DEC-1 to DEC-4 (proposal), PD-1 to PD-5 (design.md).

> Derives from: EPIC `slot-uri-clash`.

Every task: test-first; task gate `make test-changed check-quality`; commit body
`Refs: slot-uri-clash <task> <PD>` (`Refs: #206` on the last commit). Builders never commit; the
lead does and ticks this file.

## 1. One stage — branch `change/slot-uri-clash`, one PR

- [x] 1.1 **unit + code** — design.md [PD-1](design.md#decisions) to PD-5, spec scenarios 1 and 3.
  First failing tests: three rows in `tests/generator/unit/test_hard_check.py`'s `FAULTS` table
  (`Fault(rule, module, old, new, element)`), rule `HardRule.SLOT_IRI` (they fail first on the
  missing enum value, then on no problem reported), all in module `books.yaml`:
  (a) old `"slots:\n  isbn:\n"`, new `"slots:\n  parts:\n    title: Parts\n    description: Its own.\n    slot_uri: dcterms:hasPart\n  isbn:\n"`,
  element `parts` (against the toolkit's `has_part`, `rp_collections`);
  (b) old `"slots:\n  isbn:\n"`, new `"slots:\n  note:\n    title: Note\n    description: Its own.\n  isbn:\n"`
  (no `slot_uri`: its default IRI `lib:note` is the `slot_uri` of `notes`, `books.yaml:177`),
  element `note`;
  (c) old `"        title: Shade\n"`, new `"        title: Shade\n        slot_uri: lib:shelf\n"`
  (the attribute `shade` on the `slot_uri` of `shelf`, `books.yaml:186`), element `shade`.
  Then one test `test_two_slots_on_one_iri_are_named_with_their_modules_and_the_iri_and_nothing_is_written`,
  shaped as `test_a_run_with_a_default_instance_over_a_type_exits_1_naming_the_slot_and_writes_nothing`
  (`test_hard_check.py:435`), on fault (a): `rp-generate` exits 1, the message holds `parts`,
  `books`, `has_part`, `rp_collections` and `http://purl.org/dc/terms/hasPart` (PD-4's worked
  example, design.md *Algorithm*), and nothing is written. Then `slot_iri` in `HardRule` of
  `rdf_persistence_generation/model/rp_generation.yaml` (title, description, meaning
  `rp:HardRuleSlotIri`, as `toolkit_slot_name` at line 1697), `make generate`, and
  `_slot_iri_problems` in `rdf_persistence_generation/checks/hard.py`, called from `hard_problems`
  after `_slot_name_problems`. Accept: the rows and the test pass;
  `test_the_toy_library_passes` and `test_the_toolkits_own_schemas_pass` pass unchanged (spec
  scenario 2); task gate green; RISK-3's list of tripped tests, or "none", in the report.
- [x] 1.2 **docs** — after 1.1. `docs/modules/ROOT/pages/architecture/generation.adoc`: a list item
  for rule `SLOT_IRI` right after the item that names rule `TOOLKIT_SLOT_NAME`, in its style;
  `CHANGELOG.md` under `[Unreleased]` only, in the section design.md D-1 names (RISK-1): models
  with two slots on one IRI are now refused, and how to fix them. Accept: `make check-docs` green.
- [ ] 1.3 **lead** — scenario-map rows for the three new rows; `make check-all`; one review pass
  (TINY); PR into `develop`, merged on green CI; #206 closed; archive.

## Roadmap

- [x] 1.1 · [x] 1.2 · [ ] 1.3

## Verification

`make test-generator` and `make check-all` green; the toy library and the toolkit pass unchanged;
the clarity gate on this PLAN ≥ 9/10 before 1.1.
