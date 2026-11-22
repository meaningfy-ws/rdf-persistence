<!-- Parents: issue #274; openspec/specs/rp-uml-import ("The toolkit is reused, not redefined");
     archive/2026-11-20-collection-has-part and #241 (the member class a dct:hasPart role fixes).
     Serves: MWB2 v2-02 phase B (mapping-workbench-v2 PR #101) (D-12).
     Retrospective: written on 2026-11-22 after the fix was merged (PR #287, 1cb96dd). The work ran
     as a bug-fix session, not an epic session, so it had no PLAN gate. -->

# EPIC: An abstract collection leaves its member class to its subclasses

## Appetite

**TINY.** One converter function in `rdf_persistence_generation/uml/slots.py`, its tests, and one
paragraph on the UML conventions page.

## Why

Since #241 the converter fixes `member_class` (`equals_string`) on every reference collection
that has a `dct:hasPart` role to a converted class, an abstract parent included. Suppose a
concrete subclass draws its own, narrower role: an abstract `Collection` → `Resource` and
`Shelf` → `Book`. Then each class gets an `equals_string`. The values contradict each other,
and the generated `Shelf` narrows `Literal["Resource"]` to `Literal["Book"]`, so
`rp-generate --check` fails its type check. The consumer's model has an abstract `Collection`
with five concrete collections, which gave five type errors and blocked MWB2 v2-02 phase B.

## Solution outline

When a subclass fixes its own member class, the abstract parent's role stops being a member role.
It stays the toolkit's `has_part` and is reported as `toolkit-slot-kept` with its range, and each
subclass keeps its own `member_class`. A subclass's member class that does not descend from its
parent's is a converter problem that names both.

## Key decisions

- **DEC-1:** option 1 of #274: only the subclasses fix `member_class`. Rejected: option 2, a looser
  type on the parent's `member_class`, because it changes the generator's typing to work around
  a converter output.
- **DEC-2:** the parent's role is dropped only when a subclass draws its own. An abstract
  collection whose subclasses draw none keeps its member class, so they inherit it.
- **DEC-3:** a subclass's member class must descend, through domain `is_a`, from the parent's.
  Otherwise the run fails with a `toolkit_slot` problem that names the subclass, its class, the
  parent and the parent's class (#274 "Expected").
- **DEC-4:** a concrete parent is left as it is. Dropping its member class would weaken its own
  instances, and #274 does not ask for it.

## Rabbit-holes

- The descent check follows domain `is_a` only. A member class linked only through mixins is not
  a descendant.

## No-gos

- No change to the generator's typing of `member_class`.
- No change for concrete parent collections (DEC-4).

---

## What Changes

- `uml/slots.py`: `_member_roles` filters its roles through the new `_without_narrowed_parents`.
  `_lineage` walks domain `is_a`.
- Tests: three `ROWS_MEMBER_CLASS` rows (`tests/generator/unit/test_uml_rules.py`) and the
  integration test `test_an_abstract_collection_narrowed_by_its_subclass_type_checks`, which
  type-checks the converted shape.
- Docs: `reference/uml-conventions.adoc#member-class` gains the rule with a UML snippet and the
  LinkML it becomes (P-0014), and a troubleshooting row.

## Capabilities

### Modified Capabilities

- `rp-uml-import`: "The toolkit is reused, not redefined" states the abstract-parent rule and
  gains the scenario "an abstract collection narrowed by its subclasses".

## Impact

Converter output for models that have an abstract collection with narrowing subclasses. The
consumer's converted schema loses the parent's `equals_string`; no stored data changes.

## As built

Delivered in one PR, #287 (merge `1cb96dd`), as shaped. DEC-1 to DEC-4 hold.
- Proof: the integration test fails on the parent commit and passes with the fix. On MWB2's
  phase-B `.qea`, `rp-generate --check` went from 5 type errors to none.
- Gates: `make check-all` and `make test-containers` green, CI green.
- Follow-up found on the way: #290 (`make refresh-map` collects no ids).
- Retrospective spine: this change was written and archived after the merge, at the developer's
  request (2026-11-22).
