# Seeds: narrowed-slot-override (secondary; never groomed)

Captured 2026-11-27 by the planner. The EPIC (`proposal.md`) is the shaped truth.

## The owner's brief

Shape and plan a TINY change for #417 under its own OpenSpec change (P-0020), shipped before the
other changes planned the same day (`consumer-write-rules`, `typescript-toolkit-modules`), because
it blocks MWB2's EA round 26 merge (`feature/ea-round-26`). The owner accepted the planner's
recommendations; no risk is accepted.

## Issue #417: a subclass narrowing an inherited multivalued slot to one generates a field mypy rejects

Since #304 (fixed by `consumer-gap-fixes`, PR #330), a subclass that narrows an inherited `0..*`
slot to exactly one gets `multivalued: false`, `required: true` and the narrower `range` in its
`slot_usage`. `rp-generate` writes a Pydantic field on the subclass whose type does not fit the
parent's, and mypy rejects the generated module with the toolkit's own `mypy-generated.ini`:

```
mwb2/domain/generated/mwb2_resources.py:67: error: Incompatible types in assignment (expression has type "str", base class "Collection" defined the type as "list[str] | None")  [assignment]
```

```python
class Collection(ReferenceCollection):
    has_version: _Optional[list[str]] = _Field(default=None, ...)

class OntologyCollection(Collection, Tracked, Described, AggregateRoot):
    has_version: str = _Field(default=..., ...)
```

Reproduction: abstract `A` with optional multivalued `p`; `B` with `is_a: A` and
`slot_usage: p: {range: W, required: true, multivalued: false}`; `rp-generate`, then mypy with
`mypy-generated.ini`. Suggested fix: where a subclass's field type is not a subtype of the
inherited one, emit `# type: ignore[assignment]` on the override, or another shape mypy accepts;
add a type-check test on the reproduction. MWB2 (EA round 26, E-29, S7-1, on v0.15.0) does not
edit generated code or work around the toolkit.

## What the code says (read 2026-11-27, `develop` at 801613ba, v0.16.0)

- `rdf_persistence_generation/extensions/pydantic_split.py`: `after_generate_slot` builds an
  `InternalAttribute` with `loosens=_loosens_a_base_slot(slot.source, sv)`. That predicate is true
  only when the slot is optional where an ancestor's is required (PD-11 of `mwb2-file-resources`,
  #59). A multivalued-to-single narrowing is not covered. The source is unchanged since v0.15.0.
- `rdf_persistence_generation/templates/pydantic/attribute.py.jinja` ends the field line with
  `  # type: ignore[assignment]` when `loosens` is true. The mechanism exists; only the predicate is
  too narrow.
- `rdf_persistence_generation/mypy-generated.ini` sets `warn_unused_ignores = False` and the
  pydantic plugin. It ships in the package: `rp-generate --check` runs it over every target's
  package (`checks/importable.py` `type_problems`, #242), so MWB2's `--check` fails too, not only
  `make typecheck-generated`.
- Tests: `tests/generator/unit/test_ext_pydantic_split.py`
  `test_a_field_an_unlabelled_class_relaxes_carries_a_type_ignore` pins the ignore on the toy's
  `Chapter.label`, and only there. `tests/generator/integration/generated_project.py` writes a
  small project and runs mypy over it (`mypy_output`), used by `test_generated_code_imports.py`.
- TypeScript: interfaces do not `extend` (each lists every induced slot), so a narrowing is not a
  TypeScript type error. Out of this change.
- `pydantic_validators.py`: a `unique_keys` validator is written on a class with a multivalued slot
  valued by objects; a subclass inherits its parent's validators.
