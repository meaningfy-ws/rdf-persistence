# Design: narrowed-slot-override

> Derives from: EPIC `narrowed-slot-override` (proposal.md, DEC-1 to DEC-4). Facts: `inputs/seed.md`;
> the owner's answers: `inputs/qa.md`. Revised after gate run 1 (8 gaps, `evidence/clarity-gate.md`).

## Context

`SplitPydanticGenerator.after_generate_slot` (`rdf_persistence_generation/extensions/pydantic_split.py`)
builds an `InternalAttribute` with `loosens=_loosens_a_base_slot(slot.source, sv)`, and
`templates/pydantic/attribute.py.jinja` ends the field line with `  # type: ignore[assignment]`
when `loosens` is true. `_loosens_a_base_slot` is true only when the slot is optional where an
ancestor's is required (PD-11 of `mwb2-file-resources`). #417's narrowing (an optional list in the
parent, a required single value in the subclass) is not covered, so the line goes unmarked and
mypy reports `[assignment]`. `slot.source` is the class's induced slot (`owner` set), so
`sv.induced_slot(slot.name, ancestor)` gives each ancestor's view of the same slot.

A second defect sits behind the first: `templates/pydantic/unique_keys_validator.py.jinja` iterates
`for item in self.<slot> or []`. The validator is written on the class that declares the
multivalued slot (`pydantic_validators._unique_keys_validators`, `keyed_slots` keeps multivalued
slots only), and a subclass inherits it. When the subclass narrows that slot to one inlined object,
the inherited validator iterates a Pydantic model, which yields `(name, value)` tuples, and
`item.<key_slot>` raises `AttributeError`: certain, not a likelihood.

## Decisions

- **PD-1 The flag.** `InternalAttribute.loosens` is renamed `incompatible` (docstring: "the field's
  type is not a subtype of an ancestor's; the template marks the line"), and the template's
  condition reads `{%- if incompatible %}`. `_loosens_a_base_slot` is renamed
  `_overrides_incompatibly(slot, sv) -> bool`. Places that change: the attribute, the call in
  `after_generate_slot`, the template (PD-6), and the test message at
  `test_ext_pydantic_split.py:314`.
- **PD-2 The rule.** `_overrides_incompatibly(slot, sv)` returns False when `slot.identifier`,
  `slot.key` or `slot.owner is None` (as today). Otherwise, for each ancestor `a` in
  `sv.class_ancestors(slot.owner, reflexive=False)` (`is_a` and mixins) with
  `slot.name in sv.class_slots(a)`, with `base = sv.induced_slot(slot.name, a)`, the override is
  incompatible when any of:
  1. `base.required and not slot.required` (today's PD-11 case);
  2. `bool(base.multivalued) != bool(slot.multivalued)` (#417, and single → many);
  3. both are multivalued and `slot.range != base.range`: a list is invariant, so `list[B]` over
     `list[A]` is rejected by mypy even when `B is_a A`;
  4. both are class ranges and the inlining differs: for single-valued slots
     `bool(base.inlined) != bool(slot.inlined)` (an object against an IRI `str`); for multivalued
     slots, also `bool(base.inlined_as_list) != bool(slot.inlined_as_list)` (a list against a
     `dict`);
  5. both are single-valued, the ranges differ, and `slot.range` is not under `base.range`: for two
     classes, `slot.range not in sv.class_descendants(base.range)` (reflexive); for two types,
     `base.range not in sv.type_ancestors(slot.range)` (reflexive; `type_ancestors` follows
     `typeof`, so a custom `typeof: string` type is under `string`, while the built-in `uri` is
     not); for two enums, the names differ; a class against a type, a class against an enum, and a
     type against an enum, either way, are incompatible.
  It returns True on the first incompatible ancestor. No Python type string is compared (DEC-2).
  `slot.range` and `base.range` fall back to the schema's `default_range` when unset, as the
  induced slots already do.
- **PD-3 Nothing else moves.** The narrowed field keeps the type the stock generator writes (DEC-1);
  `mypy-generated.ini`, the TypeScript, SHACL, JSON Schema and OpenAPI steps are untouched (no-gos).
- **PD-4 Docs.** `CHANGELOG.md` `[Unreleased]` *Fixed*: "a subclass that narrows an inherited list
  slot to one value (or changes its range to one not under the parent's) generates a field mypy
  accepts, and an inherited unique-key check accepts the single value (#417)". The builder searches
  `docs/` for `type: ignore`; a passage on generated overrides gets one sentence, none → no page
  edit.
- **PD-5 The inherited unique-key check takes one value.** `unique_keys_validator.py.jinja`
  iterates the slot's value as a list whether it holds a list, one object or nothing:
  `value = self.{{ slot }}` then
  `for item in value if isinstance(value, list) else ([] if value is None else [value]):`.
  One object cannot repeat a key, so a narrowed subclass passes; a list behaves as today. mypy
  accepts it on the parent (`Optional[list[X]]` narrowed by `isinstance`). Rejected: generating an
  overriding no-op validator on the narrowing subclass (cross-class bookkeeping in
  `pydantic_validators.py` for a rule one template line covers); refusing a narrowing of a keyed
  slot at generation (forbids a valid model, #304's purpose).
- **PD-6 The mark is on the statement's first line.** mypy reports an `[assignment]` error on the
  first line of a multi-line assignment and honours a `# type: ignore` on that line only. The one
  branch of `attribute.py.jinja` that breaks a field over two lines (`equals_number`, a newline
  before `, le=…, ge=…`) loses its newline, so every generated field is one line and the mark
  always lands on the line mypy reports. No toolkit or toy generated file has an `equals_number`
  field today (checked: no `^    , le=` line), so only manifests change. Rejected: writing the
  comment inside the open `_Field(` on the first line (legal Python, but a comment mid-call that
  any later template edit can split).

## Algorithm / approach

Worked example (#417). `Collection.has_version`: optional, multivalued, range
`TargetOntologyVersion` (an IRI reference). `OntologyCollection` (`is_a: Collection`) has
`slot_usage: has_version: {range: TargetOntologyVersion, required: true, multivalued: false}`.
For `OntologyCollection.has_version`: ancestor `Collection`, `base.multivalued` True,
`slot.multivalued` False → rule 2 → incompatible. The line becomes
`has_version: str = _Field(default=..., ...)  # type: ignore[assignment]`; mypy accepts it.

Compatible example (spec scenario 2). Parent `p: Optional[A]` (single, inlined class `A`); child
narrows `range: B` with `B is_a A`, same multiplicity, inlining and requiredness → no rule fires →
no mark; mypy accepts a covariant attribute override (its `mutable-override` check is off by
default).

Unique key (spec scenario 3). Parent `Holder.parts`: multivalued, inlined `Part` with
`unique_keys: by_code: [code]`; `OnePartHolder` narrows `parts` to one required `Part`. The
inherited `unique_keys_parts_by_code` reads `value = self.parts`, a `Part`, iterates `[value]`,
finds no repeat, returns.

## Error matrix

| Input / state | Behaviour |
|---|---|
| Optional where an ancestor requires it (PD-11, toy `Chapter.label`) | marked (rule 1) |
| Multivalued in the ancestor, single in the subclass (#417) | marked (rule 2) |
| Single in the ancestor, multivalued in the subclass | marked (rule 2) |
| Both multivalued, class range narrowed to a subclass | marked (rule 3, list invariance) |
| Both single, class range under the ancestor's, same inlining and requiredness | not marked |
| Same class range, inlined in one and a reference in the other | marked (rule 4) |
| Both multivalued, same class range, `inlined_as_list` differs (list against dict) | marked (rule 4) |
| Both single, class range not under the ancestor's | marked (rule 5), even for an IRI reference whose Python type is `str` on both sides: a used-or-unused ignore is harmless (`warn_unused_ignores = False`), and DEC-2 forbids string comparison |
| Both single, custom type `typeof: string` against `string` | not marked (rule 5: `string` is in its `type_ancestors`) |
| Both single, `uri` against `string` | marked (rule 5: `type_ancestors('uri') == ['uri']`); harmless as above |
| Both single, type against enum, class against type or enum | marked (rule 5) |
| Both single, enum other than the ancestor's enum | marked (rule 5) |
| Identifier or key slot | never marked (as today) |
| Slot redeclared identically in the subclass | not marked |
| A mixin ancestor declares the slot incompatibly | marked (ancestors include mixins) |
| A narrowed field with `equals_number` | one line (PD-6), marked on it |
| A parent unique key over a multivalued inlined slot the subclass narrows to one | the inherited validator iterates `[value]` and passes (PD-5) |
| The same with the narrowed value absent (optional) | iterates `[]` and passes (PD-5) |

## Anti-patterns

- Comparing the rendered `range` strings (`_Optional[list[str]]` vs `str`): aliases and wrappers
  break it (DEC-2).
- Marking every redeclared field: hides real type errors in generated code.
- Editing a generated file or `mypy-generated.ini` to pass the check.
- Treating a range under the ancestor's as compatible inside a list (lists are invariant).

## Test plan

| TC | Scenario | Proof | Tier / lane |
|---|---|---|---|
| TC-1 | spec 1 | a generated project (`tests/generator/integration/generated_project.py` helpers): abstract root `Holder` with optional multivalued `has_part` over a root class `Part`; `OnePartHolder` (`is_a: Holder`) narrows it to `required: true`, `multivalued: false`; `main(["--project", ...]) == 0` and `mypy_output(project) == ""`. Fails today with the `[assignment]` error of #417 | generator integration, `test_generated_code_imports.py`, `make test-generator` |
| TC-2 | spec 1, 2 | unit, `render_modules` on a small schema (as `test_an_enum_declared_in_another_module_is_imported_not_repeated`), parametrised; each case asserts the field's line ends with the mark or not. Marked: list → single; single → list; both lists, range narrowed to a subclass; same class range, inlined against reference; both lists, `inlined_as_list` differs; enum range changed; type against enum; a mixin parent declares the slot as a list the class narrows. Not marked: single class range narrowed to a subclass; custom `typeof: string` type against `string`; unchanged redeclaration | generator unit, `test_ext_pydantic_split.py` |
| TC-3 | regression | `test_a_field_an_unlabelled_class_relaxes_carries_a_type_ignore` passes unchanged (message reworded only) | generator unit |
| TC-4 | spec 3, PD-5 | TC-1's project gains a root `KeyedHolder` with a multivalued inlined `parts` over `Part` (`unique_keys: by_code: [code]`) and `OneKeyedHolder` narrowing `parts` to one required `Part`. Generation succeeds; `OneKeyedHolder(..., parts=Part(code="a"))` validates; `KeyedHolder` with two parts of code `a` is still refused; mypy clean. Fails today with `AttributeError` | generator integration |
| TC-5 | PD-6 | unit: a parent multivalued integer slot narrowed to one with `equals_number: 1`: the generated field is one line, ends with the mark; TC-1's project gains the same field and stays mypy-clean | generator unit + integration |
| TC-6 | gate | `make check-generated` clean; `make typecheck-generated` clean | `make check-all` |

## Risks

- **RISK-1 the wider rule marks a toolkit or toy field it did not mark before.** Likelihood low,
  impact low (a comment). Mitigation: the lead's task 1.3 runs `make generate` and reports every changed
  generated `.py` line; any mark outside a real incompatible override is a PD-2 bug, fixed before
  the PR.
- **RISK-2 PD-5 changes every generated unique-key validator.** Certain for the toolkit's and
  the toy's keyed classes, impact low (same behaviour for a list). Mitigation: the existing
  unique-key tests pass unchanged (`make test-generator`, the feature lane), and TC-4 checks a list
  is still refused on a repeat.
- **RISK-3 MWB2 has more narrowings than the one reported.** Likelihood medium. Mitigation: the
  rule is general (PD-2), and the PR asks MWB2 to run `rp-generate --check` on EA round 26 against
  the branch before the merge (D-12).

## Lanes for moved or rewritten tests

None moved. TC-3's assertion message is reworded; it stays in the generator unit lane. TC-1, TC-4
and TC-5's integration half run in the generator integration lane, TC-2 and TC-5's unit half in the
generator unit lane, all in `make test-generator`.

## Delivery decisions

The lead's, taken in the epic session (R-0007), for the developer to validate at the end.

- **D-1 Own seed and index.** The shaping session's `make test-seed` was cut off mid-run and is
  invalid; the lead ran its own `make reindex` and `make test-seed` at stage start.
- **D-2 `uv sync --all-extras` in the worktree.** The worktree's `.venv` lacked the `linkml` extra,
  so no generator test could be collected (builder 1.1's report). The lead synced it (only the
  lead runs `uv sync`) and seeded again.
- **D-3 Regenerate before the generator tests run.** The freshness guard
  (`rdf_persistence_generation/testkit/freshness.py`, loaded by `tests/conftest.py`) stops every
  test session once a generator input differs from `rp-manifest.json`, so task 1.3's
  `make generate` cannot wait until after 1.2: the lead runs it after each task that edits the
  extension or a template (1.1, 1.2), before the builder's green run. 1.3's acceptance (RISK-1)
  is checked on the final regeneration.
- **D-4 Task 1.4 beside 1.1.** Disjoint files (`CHANGELOG.md` only), so it ran in parallel.
- **D-5 One seed failure, not this change's.** The seed ran 10 499 passed, 1 failed:
  `tests/unit/tooling/test_lanes.py::test_on_ci_pytest_runs_unqueued_with_the_workers_counted_by_make`,
  which passes alone and touches nothing this change edits. The seed data stands; the test is
  watched in `make check-all`.
