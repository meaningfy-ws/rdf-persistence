## ADDED Requirements

### Requirement: A subclass that narrows an inherited role keeps the narrowed multiplicity

When a class redraws an inherited association role with other multiplicity limits than its
ancestor's, the converter SHALL write each differing `required` and `multivalued` limit into that
class's `slot_usage`, `false` included, so that the class's induced slot has the redrawn limits.

#### Scenario: an inherited 0..* role narrowed to 1
- **GIVEN** an abstract class `A` with a role `p 0..*` to `V`, and a «root» class `B` generalising `A` that redraws `p 1` to `W`, a subclass of `V`, with `unique_key = k: p`
- **WHEN** the model is converted and generated
- **THEN** `B.slot_usage.p` has `range: W`, `required: true` and `multivalued: false`, and the key `k` is accepted

#### Scenario: an inherited required role made optional
- **GIVEN** `A` with a role `p 1..1`, and `B` generalising `A` that redraws `p 0..1`
- **WHEN** the model is converted
- **THEN** `B.slot_usage.p` has `required: false`

#### Scenario: agreeing usages write no limit
- **GIVEN** every usage of a slot is single-valued
- **WHEN** the model is converted
- **THEN** no `multivalued` is written for it
