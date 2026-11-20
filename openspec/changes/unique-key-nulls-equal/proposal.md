<!-- Parents: issue #202 (inputs/seed.md); openspec/specs/rp-aggregate-store (unique keys);
     rp-generation hard checks (rdf_persistence_generation/checks/hard.py). Serves: MWB2
     v2-04-source-intake task 3.7 (stage C) and v2-05-target-and-fragments task 6.1 (D-12).
     Seeds: inputs/seed.md. Consumer triage in ../uml-to-linkml/inputs/qa.md. -->

# EPIC: Unique keys where an absent optional slot counts as a value

## Appetite

**SMALL.** One option allowed in the existing unique-key guard, plus removing the hard check that
refuses it today.

## Why

In a unique key, an absent optional slot claims nothing, so two "Dune" books with no subtitle are
both accepted. SQL offers `NULLS NOT DISTINCT` for this case. The consumer needs it before `v2-04`
stage C and `v2-05`. A consumer-side pre-check would race.

## Solution outline

`consider_nulls_inequal: false` on a `unique_keys` entry with `rp_unique_scope: tenant` is
accepted. The guard then claims a distinct "absent" marker for each missing slot, in the same
guarded update as the present values. `key_duplicates()` reports conflicts on it. Keys without the
option behave as today.

## Key decisions

- **DEC-1:** the standard LinkML field `consider_nulls_inequal: false` is the switch. Rejected: a
  toolkit annotation, since LinkML already names this.
- **DEC-2:** tenant scope only, matching the consumer's need. Any other scope keeps the hard check's
  refusal, with a message naming the supported scope.
- **DEC-3:** the absent marker is one fixed toolkit IRI, never a value an application can store, so
  it cannot collide with a real value.

## Rabbit-holes

- Existing data: turning the option on for a key with stored duplicates. `key_duplicates()` reports
  them, and no automatic cleanup is offered.
- Multi-valued slots in a key stay as they are (the PLAN confirms the current rule).

## No-gos

- No new uniqueness scopes, no partial or conditional keys.
- No change to keys without the option.

---

## What Changes

- `checks/hard.py`: the refusal is lifted for tenant scope.
- Unique-key guard and `key_duplicates()`: the absent marker.

## Capabilities

### Modified Capabilities

- `rp-aggregate-store`: unique keys may treat absent values as equal.
- `rp-generation`: the hard check accepts the option at tenant scope.

## Impact

Generator hard check, the store's guarded write, docs (unique keys how-to). The UML converter
already writes the option (`uml-to-linkml` DEC-3).
