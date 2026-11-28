## ADDED Requirements

### Requirement: A root may depend on another root

An aggregate root class, or an abstract class whose concrete subclasses are aggregate roots, MAY
carry the annotation `rp_dependent_on: <slot>`, naming its pointer slot to its whole. Such a class SHALL be a dependent aggregate: an aggregate in every respect (own
graph, version token, `rp_path`, API resource, access) that cannot exist without its whole and is
deleted with it. The annotation SHALL be read from the first class of the `is_a` chain that
carries it; a mixin's annotation SHALL NOT count.

#### Scenario: a dependent result
- **GIVEN** `AuditResult` annotated `rp_dependent_on: of_audit`, `of_audit` ranging over `Audit`
- **WHEN** the schema is generated
- **THEN** `AuditResult` is an aggregate root dependent on `Audit` through `of_audit`

#### Scenario: a subclass is dependent too
- **GIVEN** a subclass of `AuditResult` by `is_a` without the annotation
- **WHEN** the runtime reads the schema
- **THEN** the subclass is dependent on `Audit` through `of_audit`
