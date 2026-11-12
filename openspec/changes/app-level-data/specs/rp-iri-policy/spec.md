## ADDED Requirements

### Requirement: The application space has its own IRI

The IRI policy SHALL mint the application space's IRI from its `application` template (default
`{base}app`), and SHALL mint the application's aggregates, parts, loaded graphs, `meta` and
`registry` from the existing templates with `{tenant}` the application IRI and `{tenant_id}` the
word `app`. `app` SHALL never be drawn as a tenant id. Building `Iris` SHALL refuse a policy whose
application IRI reads as a tenant IRI. A recorded policy without the `application` template SHALL
compare equal to one with the default.

#### Scenario: the default application IRI
- **GIVEN** settings with base `https://ex.org/` and no `iri_policy`
- **WHEN** an application aggregate of a class with `rp_path` `templates` is minted
- **THEN** its IRI is `https://ex.org/app/templates/` followed by a UUID

#### Scenario: an existing deployment upgrades
- **GIVEN** a system database whose recorded policy predates the `application` template
- **WHEN** the service starts with the default `application` template
- **THEN** the start-up check passes

#### Scenario: a colliding application IRI
- **GIVEN** a tenant template `{base}{tenant_id}` and an application template `{base}app`
- **WHEN** `Iris` is built
- **THEN** it is accepted, because `app` is reserved and never a tenant id
- **AND** an application template `{base}x7k2m9p` under 7-character tenant ids is refused with `InvalidIri`
