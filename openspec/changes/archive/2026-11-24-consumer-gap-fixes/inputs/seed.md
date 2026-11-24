# Seeds (secondary, never groomed): issues #304, #306, #311, #312, verbatim, read 2026-11-24

## #304 rp-uml2linkml: a subclass narrowing an inherited 0..* role to 1 stays multivalued, so a unique key on it is refused

## What happens
When a «root» subclass redraws an inherited role with upper multiplicity `1` (narrowing the parent's `0..*`), the converter writes the slot_usage without `multivalued: false`. `_shape_kwargs` in `uml/slots.py` drops false flags, so the slot inherits `multivalued: true`. rp-generate then refuses a unique key over that slot:

```
[unique_key] B: … slot 'p' is multivalued
```

## Reproduction
1. Abstract class `A` with an association role `p 0..*` to class `V`.
2. «root» class `B` generalising `A`, redrawing the role `p 1` to a subclass `W` of `V`.
3. Tag `B` with `unique_key = k: p`.
4. Convert, then run `rp-generate`.

Expected: `B.slot_usage.p` has `range: W`, `multivalued: false` and `required: true`, and the key `k` is accepted.
Actual: `multivalued` is not written, the slot is multivalued, and the key is refused.

## Why it matters
Narrowing an inherited role to exactly one is the usual way to say "each B belongs to exactly one W, and at most one B per W"; without it the uniqueness cannot be expressed.

## Suggested fix
In the slot_usage written for a narrowed role, write `multivalued: false` explicitly whenever the parent's slot is multivalued and the redrawn upper bound is 1. A test on the reproduction above.

## #306 set_grants does not validate role names, unlike PUT …/grants

## Summary

`Tenancy.set_grants` does not check that a grant's role is a defined tenant role. The generic `PUT …/grants` route does (`AccessRules.validate_grants`, `router.py:323` at v0.9.0), so the two write paths for grants disagree.

## Context

Consumer: MWB2, change `v2-06-roles-and-workflow` (rdf-persistence v0.9.0). MWB2's add-member route builds grants from a list of role names and calls `set_grants`. That path runs only the consumer's grant validators. A grant naming `admin` (a system role) or an undefined name is stored. From then on every `PUT …/grants` for the tenant fails with `UnknownRole`, because the stored set no longer validates.

## Expected behaviour / proposed capability

`set_grants` runs the same role validation as the grants route, before the consumer's grant validators, and refuses the write the same way.

## Acceptance

- `set_grants` with a grant naming an undefined role, or a role defined at another level, is refused and stores nothing.
- The grants route and `set_grants` give the same refusal for the same input.

## Impact on the consumer

MWB2 calls the public `kit.rules.validate_grants` itself before `set_grants` until this lands (`v2-06-roles-and-workflow` design P-3, finding T-1).


## #311 howto/workflow.adoc imports state_iri, which the top level does not export

The how-to `docs/modules/ROOT/pages/howto/workflow.adoc` (v0.9.0) imports `state_iri` from a submodule; the top-level `rdf_persistence` does not export it. A consumer that may import only the top level cannot follow the example.

Either export `state_iri` at the top level, or have the how-to build the state IRI by the documented rule (`{workflow id}/{state name}`), which is what MWB2 does (change `v2-06-discussion`, finding T-2; also `v2-06-cm-review` P-2).


## #312 find(cls, slot=None) cannot match aggregates without the slot

## Summary

`Session.find(cls, slot=None)` cannot select aggregates that have no value for an optional slot. The filter renders `None` as the literal `"None"` (`_text` → `str(Literal(value))`, `session.py` at v0.9.0), so it matches nothing; leaving the slot out matches every value.

## Context

Consumer: MWB2, change `v2-06-coverage-and-checks` (rdf-persistence v0.9.0). Before forking an ontology fragment, MWB2 looks for an existing fragment with the same class path, property path and *no* filter expression (the fragment key counts an absent filter as a value, #202). It cannot ask for "no filter expression".

## Expected behaviour / proposed capability

`find(cls, slot=None)` (and the listing's equivalent) matches aggregates without a value for `slot`, consistent with unique keys that count an absent value (#202).

## Acceptance

- Two stored aggregates, one with `slot` set and one without: `find(cls, slot=None)` returns only the second.
- Other filters combine with it as today.

## Impact on the consumer

MWB2 omits the filter and narrows the candidates itself (`v2-06-coverage-and-checks` §4.3).


