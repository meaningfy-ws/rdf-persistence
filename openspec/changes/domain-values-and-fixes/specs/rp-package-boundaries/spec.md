## ADDED Requirements

### Requirement: The domain layer may import a value module

A domain module SHALL be allowed to import a module annotated `module_kind: value`, which is a
domain-layer module; it SHALL still not import a technical or an access module, directly or through
a value module.

#### Scenario: a domain function returns a generated value
- **GIVEN** a domain module that imports a value module
- **WHEN** the boundary check runs
- **THEN** it reports no problem
