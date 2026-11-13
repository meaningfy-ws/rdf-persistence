<!-- Capability: rp-generation. Change: boundary-owned-hint (issue #72). -->

## ADDED Requirements

### Requirement: The REFERENCE problem names its fixes

The problem `rp-generate` reports SHALL, when a non-owned slot ranges over a class that is
neither an aggregate root nor a reference class, name the slot, its class and its range, and SHALL
name two fixes: annotating the slot `owned: true`, or making the range an aggregate root or pointing the slot at a root, `Principal` or `Activity`.

#### Scenario: a nested response class without owned
- **GIVEN** a technical module with class `Terms` whose slot `items` ranges over `Term`, not owned
- **WHEN** `rp-generate` runs
- **THEN** it fails with a REFERENCE problem whose text contains `owned: true` and names `Term`

#### Scenario: with owned
- **GIVEN** the same module with `annotations: {owned: true}` on `items`
- **WHEN** `rp-generate` runs
- **THEN** it reports no REFERENCE problem
