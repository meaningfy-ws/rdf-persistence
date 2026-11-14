## ADDED Requirements

### Requirement: The application space has its own IRI

The IRI policy SHALL mint the application space's IRI from its `application` template (default
`{base}app`), and SHALL mint the application's aggregates, parts, loaded graphs, `meta` and
`registry` from the existing templates with `{tenant}` the application IRI and `{tenant_id}` the
word `app`. `app` SHALL never be drawn as a tenant id. The application IRI SHALL never answer as a tenant:
asking for its tenant id, its database name or the tenant of its access record SHALL be refused
with `InvalidIri`. Building `Iris` SHALL refuse, with `InvalidIri`, a policy whose application IRI
reads as a tenant IRI, is not under the base, or is the toolkit's own IRI; whose application
access, meta or registry IRIs coincide; or under which an aggregate, part or loaded graph of the
application reads as a tenant IRI, or a tenant IRI as an aggregate of the application. A recorded
policy, or the manifest of a tenant dump, without the `application` template SHALL compare equal
to one with the default.

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

#### Scenario: the application's aggregates would read as tenants
- **GIVEN** an application template `{base}{tenant_segment}` and an aggregate template `{tenant}/{id}`
- **WHEN** `Iris` is built
- **THEN** it is refused with `InvalidIri`, because an aggregate of the application would be a valid tenant IRI

#### Scenario: the application IRI is not a tenant
- **GIVEN** any policy `Iris` accepts
- **WHEN** the tenant id or the database name of the application IRI is asked for
- **THEN** the answer is `InvalidIri`

#### Scenario: an older dump is restored
- **GIVEN** a tenant dump whose manifest predates the `application` template
- **WHEN** it is restored on a service with the default `application` template
- **THEN** the policy check of the restore passes
