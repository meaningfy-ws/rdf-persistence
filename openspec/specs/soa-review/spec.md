# soa-review Specification

## Purpose
The state-of-the-art review in the developer docs (`docs/modules/ROOT/pages/background/soa/`)
gives evidence-backed build-versus-reuse decision support for rdf-persistence and keeps
decided choices apart from open ones. Source change: `soa-python-rdf-orm`, archived as
`openspec/changes/archive/2026-11-05-soa-python-rdf-orm/`.
## Requirements
### Requirement: Build-versus-reuse decision support

The developer docs SHALL present, per building-block layer (L0–L6 and cross-cutting), what to
adopt, integrate, stay compatible with, or build, with each build item traceable to the
evidence that no mature component covers it (DEC-4, DEC-5, DEC-10).

#### Scenario: An architect decides what to build
- **WHEN** a system architect opens the state-of-the-art section of the developer docs
- **THEN** a build-versus-reuse page lists, per layer, the reusable components with their verdict
  and the items to build
- **AND** every reusable component appears in the tool catalogue with what it was built for, its
  origin and angle, its licence when it constrains use, and its reuse-threshold status

### Requirement: Evidence-backed findings

Every per-library and per-angle finding SHALL cite code (file and line or a GitNexus finding) or
documentation, and SHALL mark documentation claims the code does not back (DEC-1).

#### Scenario: A reader checks a claim
- **WHEN** a reader follows a finding on a library or angle page
- **THEN** the page names its evidence or the raw report that holds it
- **AND** unverified claims are labelled as such

### Requirement: Open decisions stay open

The docs SHALL distinguish decisions already taken (DEC-n in the EPIC) from options left to the
developer, which SHALL be presented as candidate ADRs or open questions with their trade-offs.

#### Scenario: A reader looks for what is decided
- **WHEN** a reader reads the integrated findings, design implications or architecture analysis
- **THEN** each design choice is either cited to a DEC-n or marked open for the developer

