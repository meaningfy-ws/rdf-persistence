<!-- Capability: rp-iri-policy. Change: message-bus (design.md PD-5). -->

## MODIFIED Requirements

### Requirement: Without a policy, IRIs are today's

When `ServiceSettings` sets no `iri_policy`, the toolkit SHALL mint and accept exactly the IRIs and
resource names it minted before this capability: `{base}{tenant_segment}/{uuid4}` for a tenant,
`{tenant}/{rp_path}/{uuid4}` for an aggregate root, `{root}/parts/{uuid4}` for an owned part,
`{root}/content/{uuid4}` for a loaded graph, `{tenant}/access`, `{tenant}/meta`,
`{tenant}/registry`, `{tenant}/provenance`, `{issuer}/users/{sub}` for a principal, and `{prefix}-t-{uuid hex}` for the
tenant's database and bucket.

#### Scenario: an application that sets nothing
- **GIVEN** settings without `iri_policy`
- **WHEN** a tenant, an aggregate, an owned part and a loaded graph are minted
- **THEN** each IRI has today's shape, and the existing IRI tests pass unchanged, with one change:
  the access record's graph is no longer an aggregate graph (it stays a valid grant target)

### Requirement: Each kind of IRI follows its configured template

With an `iri_policy`, the toolkit SHALL mint each tenant, access record, meta, registry and provenance graph,
aggregate root, owned part, loaded graph and principal from its template, filling `{base}`,
`{deployment}`, `{tenant_id}`, `{type}` and `{id}`. `{type}` SHALL be the class's `rp_iri_type`
(default: the class name in kebab case), or `content` for a loaded graph. The aggregate graph SHALL
stay `{root}/graph`.

#### Scenario: the consumer's tenant
- **GIVEN** base `http://mwb.meaningfy.ws/`, deployment `k3f9a2x`, tenant template
  `{base}project/{tenant_id}`, access template `{base}{deployment}/project/{tenant_id}`, and tenant
  ids of 7 characters over `[a-z0-9]`
- **WHEN** a tenant is created
- **THEN** its IRI is `http://mwb.meaningfy.ws/project/` followed by 7 such characters, its access
  record is `http://mwb.meaningfy.ws/k3f9a2x/project/` followed by the same id, and its database
  and bucket are named `{prefix}-t-{tenant_id}`

#### Scenario: a flat object
- **GIVEN** that policy with aggregate, part and loaded-graph templates all
  `{base}{tenant_id}/{type}/{id}`, object ids of 13 characters, and a class `OntologyFile` with no `rp_iri_type`
- **WHEN** an `OntologyFile` aggregate, one of its owned parts of class `Term`, and a loaded graph
  are minted in tenant `p4x8k2m`
- **THEN** their IRIs are `http://mwb.meaningfy.ws/p4x8k2m/ontology-file/{13}`,
  `http://mwb.meaningfy.ws/p4x8k2m/term/{13}` and `http://mwb.meaningfy.ws/p4x8k2m/content/{13}`,
  none nested under another

#### Scenario: the API path changes, the IRIs do not
- **GIVEN** a class whose `rp_path` changes from `files` to `ontology-files`
- **WHEN** new objects of it are minted
- **THEN** their IRIs keep the segment `ontology-file`, and the API serves them at the new path

### Requirement: Policies are checked when settings are made

`ServiceSettings` SHALL refuse a policy whose template uses a variable not allowed for its kind,
whose tenant, aggregate, part, loaded-graph or principal template does not end in its id variable,
whose access, meta, registry or provenance template contains neither `{tenant}` nor `{tenant_id}`, whose
aggregate template contains neither `{tenant}` nor `{tenant_id}`, whose part or loaded-graph template
contains none of `{tenant}`, `{tenant_id}` and `{root}`, or that contains a character outside
`[a-z0-9/:.-]` around its variables. Two rules span fields, which the generated models cannot state:
a template that uses `{deployment}` when no deployment slug is set, and a `random` id spec with no
length. They SHALL be refused with `InvalidIri` by `check_iri_policy`, which the service's `Iris` runs when it
is built and which a caller may run on the settings alone. A schema SHALL fail generation when two classes share an `rp_iri_type`
or one equals a reserved word. Building the service's `Iris` SHALL refuse a policy whose access,
meta, registry or provenance IRI, for the same tenant, equals another of them or the tenant IRI, or reads as an
aggregate or loaded graph. The provenance template defaults to `{tenant}/provenance`.

#### Scenario: a template without its id
- **WHEN** settings are made with aggregate template `{base}{tenant_id}/{type}`
- **THEN** validation fails naming the aggregate template

#### Scenario: colliding graphs
- **WHEN** an `Iris` is built with the same meta and registry template
- **THEN** it fails with `InvalidIri` naming both

#### Scenario: a provenance graph that collides
- **WHEN** an `Iris` is built with a provenance template equal to the registry template
- **THEN** it fails with `InvalidIri` naming both
