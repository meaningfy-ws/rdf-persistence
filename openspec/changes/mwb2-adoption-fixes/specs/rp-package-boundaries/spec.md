<!-- Capability: rp-package-boundaries. Change: mwb2-adoption-fixes (#42, DEC-4). -->

## ADDED Requirements

### Requirement: The package declares its types

The built wheel SHALL contain `rdf_persistence/py.typed` (PEP 561), so a consumer's type checker
analyses the toolkit's annotations without configuration.

#### Scenario: a typed consumer
- **GIVEN** a project that depends on rdf-persistence and has no mypy override for it
- **WHEN** mypy checks a module that imports `rdf_persistence` and `rdf_persistence.testkit`
- **THEN** it reports no `import-untyped` error, and a wrong argument type to a toolkit function is
  reported
