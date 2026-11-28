# Design: narrowed-slot-followups

> Derives from: EPIC `narrowed-slot-followups` (proposal.md, DEC-1 to DEC-3). Facts: issue #428
> (`inputs/seed.md`) and the archived `narrowed-slot-override` design (PD-2, PD-5, error matrix,
> D-8), read on `develop` at c42bc94f.

## Context

`_overrides_incompatibly` (`rdf_persistence_generation/extensions/pydantic_split.py`) returns
False for an identifier or key slot, then applies PD-2 rules 1 to 5; rule 5 calls `_is_under`,
whose class branch (`class_descendants`) and type branch (`type_ancestors`) no marked test reaches.
`test_a_field_overriding_a_slot_incompatibly_carries_a_type_ignore_and_only_then` builds `Child.s`
from a `Parent.s` and a `slot_usage` over the module `NARROWING_MODULE` (classes `A`, `B is_a A`,
enums `Colour`, `Shade`, type `Label typeof string`).

`unique_keys_validator.py.jinja` loops
`for item in value if isinstance(value, list) else ([] if value is None else [value]):`.
`keyed_slots` (`rdf_persistence/schema/services/schema_structure.py`) keeps a multivalued slot over
a class whose values are objects (`inlined`, `inlined_as_list`, or no identifier). LinkML's Pydantic
generator renders a multivalued slot with `inlined: true`, no `inlined_as_list`, over a class with an
identifier as `Optional[dict[str, X]]`, keyed by identifier. The loop then iterates `[the dict]`
and reads `item.<key>` on a dict: `AttributeError` for `{}` and for any non-empty dict.

## Decisions

- **PD-1 A dict's values are iterated (DEC-1).** The loop line becomes
  `for item in value.values() if isinstance(value, dict) else value if isinstance(value, list) else ([] if value is None else [value]):`
  on every generated unique-key validator. One line covers every shape a class or its subclass can
  give the slot (dict, list, one object, none). mypy accepts it on a parent typed
  `Optional[list[X]]` (the dict branch narrows to an unreachable type; `warn_unreachable` is off in
  `mypy-generated.ini`) and on one typed `Optional[dict[str, X]]`. Rejected: (a) refusing such a
  slot in `keyed_slots` (forbids valid LinkML; `keyed_slots` also feeds `shacl_constraints.py`
  and the conformance kit); (b) a per-validator flag `as_dict`, set where LinkML renders a dict, so
  that existing generated validators stay byte-identical: it re-derives LinkML's rendering rule in
  the extension and drifts when LinkML changes it, for the price of three regenerated lines.
- **PD-2 Mutation proves a test of working code (DEC-2).** For W1, W2 and S2 the red run is the new
  test run against the code with the branch broken by hand, as the task names; the break is
  reverted before the green run, and the builder's report quotes the failing assertion.
- **PD-3 Docs.** `CHANGELOG.md` `[Unreleased]` *Fixed*: "the generated unique-key check of a
  keyed slot rendered as a dict (multivalued, `inlined: true`, no `inlined_as_list`, over a class
  with an identifier) checks the dict's values instead of failing (#428)". The `generation.adoc`
  row of `pydantic_validators.py` says "multivalued slot", which stays true: no page edit.

## Error matrix (new or newly tested rows)

| Input / state | Behaviour | Test |
|---|---|---|
| Both single, `Parent.s` an inlined `B`, `Child.s` narrowed to `A` (not under) | marked (rule 5, class branch) | T-W1 |
| Both single, `string` against `uri` | marked (rule 5, type branch) | T-W1 |
| Both single, an inlined class against `string`, and `string` against a class | marked (rule 5, kinds differ) | T-W1 |
| Both single, an inlined class against an enum | marked (rule 5) | T-W1 |
| `Child.s` made `identifier: true` with range `uri` over `string` | not marked (rule 5 would mark) | T-S2a |
| `Child.s` made `key: true` with range `uri` over `string` | not marked | T-S2a |
| Narrowed keyed slot optional and absent | validates, iterates `[]` | T-S2b |
| Dict-rendered keyed slot, `{}` | validates (today `AttributeError`) | T-S1 |
| Dict-rendered keyed slot, two parts of different ids, same code | refused `unique_keys by_code` (today `AttributeError`) | T-S1 |
| Dict-rendered keyed slot, two parts of different codes | validates | T-S1 |
| List, one value, `None` | as today | existing TC-4 |

## Test plan

| Test | Finding | Proof (red, then green) | Tier |
|---|---|---|---|
| T-W1 | W1 | five new parametrised rows in `test_a_field_overriding_a_slot_incompatibly_carries_a_type_ignore_and_only_then`: `class-not-under` (`{range: B, inlined: true}` / `{range: A}`), `uri-against-string` (`{range: string}` / `{range: uri}`), `class-against-type` (`{range: A, inlined: true}` / `{range: string}`), `type-against-class` (`{range: string}` / `{range: A, inlined: true}`), `class-against-enum` (`{range: A, inlined: true}` / `{range: Colour}`); all marked. Red: `_is_under` returning True in its class branch fails `class-not-under`; in its type branch fails `uri-against-string`; its last line returning True fails the three kind rows | generator unit |
| T-S2a | S2 | `test_an_identifier_or_key_slot_is_never_marked`, parametrised over `identifier` and `key`: `Parent.s` `{range: string}`, `slot_usage` `{<flag>: true, range: uri, required: true}`; line unmarked. Red: delete `slot.identifier or slot.key or` from the guard | generator unit |
| T-W2 | W2 | TC-1 (`test_a_subclass_narrowing_a_list_slot_to_one_value_generates_a_package_mypy_accepts`): `SubPart` (`is_a: Part`, root class); `has_part` usage gains `range: SubPart`; a single-valued slot `main_part` over an inlinable non-root class `Piece` (no `AggregateRoot` mixin, identifier inherited from `Described` or none) with `inlined: true` on `Holder`, and `OnePartHolder` narrows it to `SubPiece` (`is_a: Piece`); the test asserts `main_part`'s generated line has no mark and `mypy_output(project) == ""`. Red, two breaks: `_overrides_incompatibly` returning False after its guard makes mypy report `[assignment]` on `has_part`; returning True fails the no-mark assertion on `main_part` (mypy alone cannot fail scenario 2, since `warn_unused_ignores` is off) | generator integration |
| T-S2b | S2 | `test_a_narrowed_keyed_slot_validates_one_value_and_a_list_still_refuses_a_repeated_key` gains `OptionalOneKeyedHolder` (`is_a: KeyedHolder`, `parts: {multivalued: false}`), built without `parts`; it validates. Red: template's `[] if value is None` replaced by `[value]` | generator integration |
| T-S1 | S1 | new `test_a_keyed_slot_rendered_as_a_dict_checks_its_values`: a project with `DictKeyedHolder.parts` (`multivalued`, `inlined: true`, no `inlined_as_list`, range `Part` with an identifier and `unique_keys by_code`); the generated field annotation contains `dict`; `parts={}` validates; two parts of different ids and codes validate; two of different ids and the same code raise `ValueError` matching `unique_keys by_code`; mypy clean. Red: today's template raises `AttributeError` on `{}` | generator integration |
| T-gold | PD-1 | the validator golden test passes after the golden file follows the new loop line | generator unit |

## Risks

- **RISK-1 LinkML does not render the S1 slot as a dict in this version.** Then T-S1's annotation
  assertion fails on the first run: the builder reports it, and the lead drops S1 as moot (records
  a D-n) instead of changing the template.
- **RISK-2 the generated project refuses `Piece` inlined in a root** (a boundary check). The
  builder uses the keyed project's `Part` pattern (a class outside the root mixins, as in
  `KEYED_CLASSES`) and reports the class used.
- **RISK-3 PD-1 changes every generated unique-key validator.** Certain, impact low: the toolkit's
  three validators and the golden file gain the dict branch; the lead's `make generate` and
  `make check-generated` show only those lines and the manifests.

## Lanes

No test moved. Unit rows run in the generator unit lane, integration ones in the generator
integration lane, all in `make test-generator`.

## Delivery decisions

- **D-1 No venv in the worktree.** The worktree was cut without a `.venv`; the builder's probe
  `uv run --no-sync` created an empty one, which it removed. No test can run until the lead runs
  `uv sync --all-extras` (only the lead runs it); the builder stopped before task 1.2.
- **D-2 S1 needs `make generate`.** Every generator file is a manifest input, so the template edit
  stops every test session under the freshness guard until the lead regenerates; T-S1's red run
  comes before the edit, and its green run after the lead's `make generate`.
- **D-3 Break runs without the freshness guard.** A deliberate break (PD-2) edits a generator
  input, so the guard would stop the session before any test ran. The break runs, and the S1
  pre-check after the template edit, ran as `uv run pytest <file> -p
  no:rdf_persistence_generation.testkit.freshness`: the tests concerned build their own project in
  a temporary folder and read no committed generated code. Every green run of record runs with the
  guard on.
- **D-4 RISK-1 and RISK-2 did not occur.** LinkML renders `parts_by_id` as `dict[...]` (T-S1's
  annotation assertion passed on the red run); `Piece` (`mixins: [Described]`, the slot
  `owned: true`) inlines in a root with no boundary refusal.
- **D-5 The golden line edited by hand.** `make refresh-golden` is stopped by the guard until the
  lead regenerates, so the one loop line of `validators.py.golden` was edited to the template's
  output; `test_ext_pydantic_validators.py` checks it (40 passed, guard off). After the lead's
  `make generate`, `make refresh-golden` left the fixture diff byte-identical (same sha256).
