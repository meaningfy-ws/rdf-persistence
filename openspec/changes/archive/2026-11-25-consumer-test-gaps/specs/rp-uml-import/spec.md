## ADDED Requirements

### Requirement: A redrawn role keeps its own cardinality bounds

When the usages of a slot differ on `minimum_cardinality` or `maximum_cardinality`, the converter
SHALL write each usage's own bound into its class's `slot_usage`: the lower bound for the minimum,
and the upper bound for the maximum when it is finite. A usage whose upper bound is unbounded while
the upper bound of an `is_a` ancestor's usage of the same slot, as its multiplicity gives it (a
single-valued `0..1` counts as 1), is finite SHALL be the problem `cardinality_unbounded`, through
any number of ancestors, those without attributes included.

#### Scenario: an unbounded role under a single-valued ancestor
- **GIVEN** `A` with `p 0..1`, `B` generalising `A` with `p 0..*`, and an unrelated `D` with `p 0..3`
- **WHEN** the model is converted
- **THEN** the run fails with the problem `cardinality_unbounded` on `B.p`

#### Scenario: an inherited 2..* role redrawn as 1
- **GIVEN** an abstract class `A` with a role `p 2..*` to `V`, and `B` generalising `A` that redraws `p 1` to `W`, a subclass of `V`
- **WHEN** the model is converted
- **THEN** `B.slot_usage.p` has `minimum_cardinality: 1`, and `SchemaView.induced_slot("p", "B").minimum_cardinality` is 1

#### Scenario: an inherited 0..5 role redrawn as 0..1
- **GIVEN** `A` with `p 0..5`, and `B` generalising `A` with `p 0..1`
- **WHEN** the model is converted
- **THEN** the induced `maximum_cardinality` of `p` on `B` is 1

#### Scenario: an unbounded role under a bounded ancestor
- **GIVEN** `A` with `p 0..5`, and `B` generalising `A` with `p 0..*`
- **WHEN** the model is converted
- **THEN** the run fails with the problem `cardinality_unbounded` on `B.p`

#### Scenario: an unrelated class may be unbounded
- **GIVEN** `A` with `p 0..5`, and a class `C` that does not generalise `A`, with `p 0..*`
- **WHEN** the model is converted
- **THEN** there is no problem, and `C` writes no maximum
