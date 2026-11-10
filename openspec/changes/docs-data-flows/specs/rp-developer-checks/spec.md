<!-- Capability: rp-developer-checks. Change: docs-data-flows. -->

## ADDED Requirements

### Requirement: The docs' diagrams render with the site's mermaid

The `Makefile` SHALL pin one mermaid version (`MERMAID_VERSION`). `make check-docs` SHALL fail when
an Antora playbook loads another mermaid version. `make check-diagrams` SHALL render every
`[mermaid]` block of every docs page with that version, and SHALL fail when one does not render.
CI SHALL run both.

#### Scenario: a playbook loads another mermaid
- **GIVEN** the `Makefile` pins mermaid 12.3.0 and a playbook loads `mermaid@10`
- **WHEN** `make check-docs` runs
- **THEN** it fails naming the playbook

#### Scenario: a diagram does not parse
- **GIVEN** a docs page with a sequence diagram whose message holds a `;`
- **WHEN** `make check-diagrams` runs
- **THEN** it fails with the parse error, and the page is not published broken
