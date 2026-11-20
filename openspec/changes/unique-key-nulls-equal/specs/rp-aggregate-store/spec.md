## ADDED Requirements

### Requirement: A unique key may count an absent value

A unique key with `consider_nulls_inequal: false` and `rp_unique_scope: tenant` SHALL treat an absent
optional slot as one value, guarded in the same update as present values and reported by
`key_duplicates()`. Keys without the option SHALL behave as before.

#### Scenario: concurrent creates with the slot absent
- **GIVEN** the key `title_subtitle` on `[title, subtitle]` with `consider_nulls_inequal: false`
- **WHEN** two concurrent creates of "Dune" with no subtitle run
- **THEN** exactly one succeeds and the other raises `KeyConflict`

#### Scenario: a present value differs
- **GIVEN** "Dune" with no subtitle is stored
- **WHEN** "Dune" / "Messiah" is created
- **THEN** it is accepted

#### Scenario: an unsupported scope
- **GIVEN** the option on a key whose scope is not `tenant`
- **WHEN** `rp-generate` runs
- **THEN** the hard check refuses it, naming the supported scope
