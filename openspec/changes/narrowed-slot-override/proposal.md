<!-- Parents: issue #417 (MWB2 EA round 26, E-29, S7-1); rp-generation "LinkML is the single source
     of every model artefact" and "Stale or edited generated output is detected" (the --check type
     step, #242); consumer-gap-fixes (#304, PR #330), which made the narrowing expressible. -->

# EPIC: a subclass may narrow an inherited list to one value and still type-check

**Golden-thread parents:** issue #417, filed by MWB2 EA round 26 (E-29, S7-1); `rp-generation`
"LinkML is the single source of every model artefact" (generated code is never edited) and the
type step of `rp-generate --check` (#242); the archived `consumer-gap-fixes` (#304), which made
the narrowing expressible; PD-11 of the archived `mwb2-file-resources`, whose override mark this
change widens. Serves the consumer's need (D-12): MWB2's EA round 26 merges once its generated
code type-checks.

## Appetite

**TINY.** One concern in one place: the predicate that marks an incompatible field override in
the Pydantic extension. No new concept, one stage, one PR.

## Why

A model may narrow an inherited role to exactly one value, the usual way to give the role a unique
key (#304). The generated subclass then redeclares the field as a single value where its parent
declares an optional list, and mypy, run by `make typecheck-generated` and by `rp-generate --check`,
rejects the module. MWB2 cannot merge EA round 26, and editing generated code is not allowed.

## Solution outline

The generator already marks one kind of incompatible override, a field a subclass makes optional
where its parent requires it, with `# type: ignore[assignment]` on that line. The same mark goes
on a field whose type is not a subtype of the inherited field's: a slot narrowed from many values
to one (or widened from one to many), or one whose range is not the inherited range or under it.
Every other field stays unmarked. A generated project reproducing #417 type-checks.

## Key decisions

- **DEC-1:** the narrowed field keeps its narrowed type and carries `# type: ignore[assignment]`,
  decided from the schema (multivalued, required, range against every ancestor's induced slot).
  Reason: the generated class says what the model says (one value, required), and the mark already
  exists for PD-11. Rejected: keeping the parent's list type on the subclass with
  `min_length=max_length=1` (the class would no longer say "one value", and every consumer reads
  `x[0]`); a validator instead of a typed field (loses the type); marking every override (hides
  real errors).
- **DEC-2:** the mark is decided by comparing LinkML facts, never by comparing the rendered Python
  type strings. Reason: the strings carry aliases (#243) and `Optional` wrappers. Rejected: string
  comparison.
- **DEC-3:** the proof is a type check of generated code: a generated project reproducing #417 is
  mypy-clean with `mypy-generated.ini`, and a unit test pins the mark on the narrowed field and
  only there.
- **DEC-4:** not breaking. Generated code gains a comment on the affected lines, and each
  unique-key validator's loop accepts one value as well as a list (PD-5); no type, field or
  behaviour changes for existing models. A consumer regenerates; nothing else.

## Rabbit-holes

- The range test: a class range under the parent's (an inlined subclass) is a subtype and needs no
  mark; an IRI reference is `str` on both sides; an enum is its own type. PD-2 fixes the rule; no
  general Python subtype engine.
- Inherited validators: a parent's `unique_keys` validator iterates its list slot; a subclass that
  narrows that slot to one object inherits it and fails. In scope: the validator takes a list or
  one value (design.md PD-5).
- TypeScript is flat (no `extends`), so no TypeScript change.

## No-gos

- Changing the narrowed field's type, or the parent's.
- Turning on `warn_unused_ignores` or changing `mypy-generated.ini`.
- A TypeScript, SHACL, JSON Schema or OpenAPI change.
- Any other `consumer-gap-fixes` or UML converter change.
- Anything of `consumer-write-rules` or `typescript-toolkit-modules` (planned the same day).

---

## What Changes

- `rp-generate`'s Pydantic step marks a field override that is not a subtype of the inherited
  field (multivalued to single, single to multivalued, a range not under the inherited one) with
  `# type: ignore[assignment]`, as it marks a loosened required slot; the mark sits on the field's
  only line.
- An inherited unique-key check accepts a slot a subclass narrowed to one value.
- Tests: a generated-project type check of the #417 reproduction; a unit pin of where the mark
  goes.
- `CHANGELOG.md` `[Unreleased]` *Fixed*.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rp-generation`: a requirement added, "A subclass that narrows an inherited slot generates code
  that type-checks".

## Impact

- Code: `rdf_persistence_generation/extensions/pydantic_split.py` (the predicate and its flag);
  `templates/pydantic/attribute.py.jinja` (the flag's name, and the `equals_number` branch on one
  line so the mark sits on the line mypy reports); `templates/pydantic/unique_keys_validator.py.jinja`
  (an inherited unique-key check accepts a single value).
- Generated code: every unique-key validator gains the list-or-one line; no other generated line
  changes unless a class overrides a slot incompatibly (task 1.3 reports any diff).
- Tests: `tests/generator/unit/test_ext_pydantic_split.py`,
  `tests/generator/integration/test_generated_code_imports.py` (or a sibling); scenario-map rows.
- `rp-manifest.json` files where the extension is a generator input; generated toolkit and toy
  code unchanged apart from PD-5's validator lines, unless one of their classes narrows a slot
  (the lead's regeneration, task 1.3, reports any diff).
- Consumers: MWB2 regenerates; `mwb2_resources.py:67` gains the mark; EA round 26 merges.

## Reconciliation (as delivered)

Delivered in PR #427 (one stage, TINY; closes #417 on merge). Decisions taken in delivery are
`design.md` D-1 to D-9. Review: one L2+L3 pass, no Critical; four findings under the floor (D-8),
follow-up #428. Acceptance: `evidence/acceptance.md`; docs owed: `evidence/docs-owed.md` (none
beyond the CHANGELOG).

| Item | Final state | PR |
|---|---|---|
| DEC-1 the narrowed field keeps its type, marked | Delivered: `_overrides_incompatibly` and its rule predicates in `extensions/pydantic_split.py`, flag `incompatible` (PD-1, PD-2) | #427 |
| DEC-2 LinkML facts, no type strings | Delivered: induced slots, `class_descendants`, `type_ancestors`; no string comparison | #427 |
| DEC-3 the proof is a type check | Delivered: TC-1 (generated project mypy-clean), TC-2 unit pins; `make typecheck-generated` green | #427 |
| DEC-4 not breaking | Delivered: generated code gains the mark where it applies (none in the toolkit or toy) and PD-5's loop in three toolkit validators; no type, field or behaviour change for a list | #427 |
| PD-5 inherited unique-key check takes one value | Delivered: `unique_keys_validator.py.jinja`; the validator golden file follows (RISK-2) | #427 |
| PD-6 one-line `equals_number` | Delivered: `attribute.py.jinja`; TC-5 | #427 |
| Spec scenario 1, list narrowed to one | Proved: TC-1 (multiplicity and requiredness; a narrower range in the same test is #428 W2) | #427 |
| Spec scenario 2, compatible override unmarked | Proved for the mark (TC-2 unmarked cases); a mypy run over it is #428 W2 | #427 |
| Spec scenario 3, inherited unique key | Proved: TC-4 | #427 |
| `CHANGELOG.md` `[Unreleased]` *Fixed* | Delivered | #427 |
| Scenario-map rows | Delivered (five rows) | #427 |
| Requirement merged into `rp-generation` | At archive | archive commit |

What Changes, Capabilities and the spec delta are true of the code. Impact as delivered: the
generated `.py` change is PD-5's lines in `rp_tenancy.py` and `rp_access_services.py` (two
validators), plus every `rp-manifest.json`; `tests/fixtures/library/golden/pydantic_validators/validators.py.golden`
joined the Impact list (RISK-2). Not delivered from the shape: the error-matrix rows of #428
(W1, S2) have no test yet; the code covers them.
