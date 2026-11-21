## MODIFIED Requirements

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
aggregate or loaded graph of that tenant. The provenance template defaults to `{tenant}/provenance`.

#### Scenario: a template without its id
- **WHEN** settings are made with aggregate template `{base}{tenant_id}/{type}`
- **THEN** validation fails naming the aggregate template

#### Scenario: colliding graphs
- **WHEN** an `Iris` is built with the same meta and registry template
- **THEN** it fails with `InvalidIri` naming both

#### Scenario: a provenance graph that collides
- **WHEN** an `Iris` is built with a provenance template equal to the registry template
- **THEN** it fails with `InvalidIri` naming both
