<!-- Parents: issue #428 (inputs/seed.md); the archived change 2026-11-27-narrowed-slot-override
     (PR #427, #417): its design.md PD-2 rule 5, PD-5, the error matrix and D-8, which deferred the
     four findings; rp-generation "A subclass that narrows an inherited slot generates code that
     type-checks". -->

# EPIC: close the review findings left by the narrowed-slot override

**Golden-thread parents:** issue #428; the archived `narrowed-slot-override` (PR #427, closes
#417), whose review pass left four findings under the floor (its design.md D-8); `rp-generation`
"A subclass that narrows an inherited slot generates code that type-checks". No consumer waits on
it: it hardens what MWB2's EA round 26 already uses.

## Appetite

**TINY.** Three test gaps and one loop line in one template; one stage, one PR.

## Why

The narrowed-slot override shipped with two rows of its error matrix and the marked side of rule 5
untested, and with no mypy run over a narrower range or a compatible override, so a regression in
those branches would pass the suite. And a keyed slot LinkML renders as a `dict` (multivalued,
`inlined: true`, no `inlined_as_list`, over a class with an identifier) breaks the generated
unique-key check: any value but `None`, an empty `{}` included, raises `AttributeError`.

## Solution outline

Each untested branch gets a case that fails when the branch is broken by hand. TC-1's generated
project narrows to a subclass range and gains a compatible covariant override, both under mypy.
The unique-key check iterates a dict's values, so a dict-rendered keyed slot is checked like a
list.

## Key decisions

- **DEC-1:** a dict-rendered keyed slot is supported: the generated unique-key check iterates its
  values. Reason: it is valid LinkML, `keyed_slots` and the SHACL constraint already treat it as
  holding objects, and the values of the dict are the objects the key is about. Rejected: refusing
  such a slot in `keyed_slots` (forbids a valid model, and `keyed_slots` also feeds the SHACL
  constraint and the conformance kit, which handle it today). Detail: design.md PD-1.
- **DEC-2:** a test of behaviour the code already has proves itself by a mutation: the builder
  breaks the branch by hand, sees the new test fail, and restores it. Reason: W1, W2 and S2 add
  tests over working code, where no red run exists otherwise.
- **DEC-3:** not breaking. A list, one value and `None` behave as today; generated validators gain
  the dict branch on their loop line.

## Rabbit-holes

- Keeping generated validators untouched by rendering the dict branch only where LinkML would
  render a dict: it re-states LinkML's rendering rule in the extension (rejected in PD-1).
- A general subtype engine for rule 5: the cases pin the existing rule, they do not widen it.

## No-gos

- Any change to PD-2's rules or `_overrides_incompatibly`'s results.
- `mypy-generated.ini`, `warn_unused_ignores`, the TypeScript, SHACL, JSON Schema or OpenAPI steps.
- Changing which slots `keyed_slots` returns.
- Editing generated files by hand (the lead regenerates).

---

## What Changes

- The generated unique-key validator iterates a dict's values; a list, one value or `None` as today.
- Tests: rule-5 cases for classes and types; identifier and key slots never marked; TC-1 narrows to
  a subclass range and adds a covariant override under mypy; an optional narrowed keyed slot left
  absent; a dict-rendered keyed slot (empty, one, a repeated key).
- `CHANGELOG.md` `[Unreleased]` *Fixed*.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rp-generation`: "A subclass that narrows an inherited slot generates code that type-checks"
  names the dict a unique-key check accepts, with one scenario.

## Impact

- Code: `rdf_persistence_generation/templates/pydantic/unique_keys_validator.py.jinja` (the loop
  line). `pydantic_split.py` is untouched: W1 and S2 pin it.
- Generated: the unique-key validators of `rp_tenancy.py` and `rp_access_services.py`, every
  `rp-manifest.json`; `tests/fixtures/library/golden/pydantic_validators/validators.py.golden`.
- Tests: `tests/generator/unit/test_ext_pydantic_split.py`,
  `tests/generator/integration/test_generated_code_imports.py`; `tests/audit/scenario-map.csv`.
