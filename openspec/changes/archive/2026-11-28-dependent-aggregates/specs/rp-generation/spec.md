## ADDED Requirements

### Requirement: A dependent class points at its whole with a required single slot

`rp-generate` SHALL fail, naming the class and the slot, when a class annotated `rp_dependent_on`
is neither a served aggregate root nor an abstract class whose concrete subclasses are all served
roots; when a subclass of a dependent class annotates another slot; or when, for any concrete
dependent class, the named slot as induced for that class is missing, not required or multivalued,
or does not range over a served root or over an abstract class whose concrete subclasses are all
served roots, or ranges over the tenant root or a root the toolkit writes. It SHALL fail when the
dependence between concrete classes, ranges expanded to their concrete subclasses, forms a cycle,
a class depending on itself included, naming the classes of the cycle in order.

#### Scenario: an optional pointer
- **GIVEN** `AuditResult` annotated `rp_dependent_on: of_audit` and `of_audit` not required
- **WHEN** `rp-generate` runs
- **THEN** it fails naming `AuditResult` and `of_audit`, and no output file changes

#### Scenario: a multivalued pointer
- **GIVEN** `of_audit` multivalued
- **WHEN** `rp-generate` runs
- **THEN** it fails naming `AuditResult` and `of_audit`

#### Scenario: a pointer over a class that is no root
- **GIVEN** `of_audit` ranging over an owned class
- **WHEN** `rp-generate` runs
- **THEN** it fails naming `AuditResult` and `of_audit`

#### Scenario: a cycle of dependence
- **GIVEN** `AuditResult` dependent on `AuditFinding` and `AuditFinding` dependent on `AuditResult`
- **WHEN** `rp-generate` runs
- **THEN** it fails naming both classes

#### Scenario: a subclass that relaxes the pointer
- **GIVEN** a concrete subclass of `AuditResult` whose `slot_usage` makes `of_audit` optional
- **WHEN** `rp-generate` runs
- **THEN** it fails naming the subclass and `of_audit`

#### Scenario: the annotation on an abstract base
- **GIVEN** an abstract `AuditResult` annotated `rp_dependent_on: of_audit` whose concrete
  subclasses are served roots
- **WHEN** `rp-generate` runs
- **THEN** it succeeds

#### Scenario: a chain of two levels
- **GIVEN** `AuditFinding` dependent on `AuditResult`, itself dependent on `Audit`
- **WHEN** `rp-generate` runs
- **THEN** it succeeds
