<!-- Secondary input, never groomed: GitHub issue #202 (meaningfy-ws/rdf-persistence), fetched 2026-11-20. The EPIC (../proposal.md) supersedes it. -->

# #202 Unique keys: let an absent optional slot count as a value (nulls not distinct)

## Summary
Unique keys across aggregates: let an absent optional slot count as a value ("nulls not distinct").

## Context
Consumers: MWB2 changes `v2-04-source-intake` (task 3.7, DEC-13) and `v2-05-target-and-fragments` (DEC-14); toolkit locked at `c671fefb` (v0.7.0).

## Current behaviour
In a unique key, an absent optional slot claims nothing, so two aggregates with the same key values and the optional slot absent are both accepted. Declaring `consider_nulls_inequal: false` is refused by the hard check (`rdf_persistence_generation/checks/hard.py`: "consider_nulls_inequal: false contradicts a missing value claiming nothing").

## Expected behaviour / proposed capability
Allow `consider_nulls_inequal: false` (with `rp_unique_scope: tenant`): the guard claims a distinct "absent" value for the missing slot, checked in the same guarded update as present values and reported by `key_duplicates()`.

```yaml
unique_keys:
  title_subtitle:
    unique_key_slots: [title, subtitle]
    consider_nulls_inequal: false
```

## Why it belongs in rdf-persistence
Uniqueness is enforced by the toolkit's guarded write; a consumer pre-check would race. SQL offers the same option (`NULLS NOT DISTINCT`).

## Acceptance
- Given the key above, When two concurrent creates of "Dune" with no subtitle run, Then exactly one succeeds and the other raises `KeyConflict`.
- Given "Dune" with no subtitle, When "Dune" / "Messiah" is created, Then it is accepted.
- Given a key without the option, Then behaviour is unchanged.

## Impact on the consumer
MWB2 cannot protect aggregates whose optional qualifier is absent from duplicates; the tasks wait.


## Comments

