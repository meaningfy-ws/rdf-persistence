## ADDED Requirements

### Requirement: LinkML may be generated from a UML class model

The LinkML a project generates from MAY itself be written by `rp-uml2linkml` from an Enterprise
Architect model instead of by hand. `rp-generate` SHALL treat that LinkML as any other schema: the
same checks, the same targets and the same freshness rules, with no step that knows where the
LinkML came from. The UML model is then the source the modellers edit, and the LinkML is
regenerated whole from it.

#### Scenario: a converted schema is generated like a hand-written one
- **GIVEN** a project whose LinkML was written by `rp-uml2linkml`
- **WHEN** `rp-generate` runs
- **THEN** it applies its lint, boundary, hard and rules steps and writes its targets exactly as for
  a hand-written schema
