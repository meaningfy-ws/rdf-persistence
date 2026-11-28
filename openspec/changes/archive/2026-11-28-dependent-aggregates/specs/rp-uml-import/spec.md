## ADDED Requirements

<!-- PD-17: once aggregate-composition is archived, this becomes a MODIFIED of the requirement that
     holds its "a generated «own graph» part is refused" scenario, which this change removes. -->

### Requirement: An «own graph» composition to a generated part converts to a dependent root

`rp-uml2linkml` SHALL convert the part of an «own graph» composition that is a generated class into
an aggregate root annotated `rp_dependent_on: <slot>`, where the slot is the association's role on
the whole's end, required, single-valued and ranging over the whole. An association with no role on
the whole's end, or whose multiplicity there is not `1`, SHALL be a problem naming it. A role on the
part's end SHALL not be converted and SHALL get a report line. `rp-generate` SHALL accept the output.

#### Scenario: a generated «own graph» part
- **GIVEN** `Audit` ◆«own graph» `AuditResult`, the association's role `of_audit` on `Audit`'s end
  with multiplicity `1`
- **WHEN** `rp-uml2linkml` runs
- **THEN** `AuditResult` is a root annotated `rp_dependent_on: of_audit`, `of_audit` is required and
  ranges over `Audit`, `Audit` has no slot listing results, and `rp-generate` accepts the output

#### Scenario: no pointer role
- **GIVEN** the same composition with no role on `Audit`'s end
- **WHEN** `rp-uml2linkml` runs
- **THEN** it fails with a problem naming the association
