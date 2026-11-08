<!-- Capability: rp-iri-policy. Change: iri-policy (GitHub issue #26). -->

## ADDED Requirements

### Requirement: Without a policy, IRIs are today's

When `ServiceSettings` sets no `iri_policy`, the toolkit SHALL mint and accept exactly the IRIs and
resource names it minted before this capability: `{base}{tenant_segment}/{uuid4}` for a tenant,
`{tenant}/{rp_path}/{uuid4}` for an aggregate root, `{root}/parts/{uuid4}` for an owned part,
`{root}/content/{uuid4}` for a loaded graph, `{tenant}/access`, `{tenant}/meta`,
`{tenant}/registry`, `{issuer}/users/{sub}` for a principal, and `{prefix}-t-{uuid hex}` for the
tenant's database and bucket.

#### Scenario: an application that sets nothing
- **GIVEN** settings without `iri_policy`
- **WHEN** a tenant, an aggregate, an owned part and a loaded graph are minted
- **THEN** each IRI has today's shape, and the existing IRI tests pass unchanged

### Requirement: Each kind of IRI follows its configured template

With an `iri_policy`, the toolkit SHALL mint each tenant, access record, meta and registry graph,
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

### Requirement: Only IRIs the policy would mint are accepted

The session SHALL refuse with `InvalidIri`, before anything is sent to the store, an aggregate root
that matches no aggregate template of its tenant with `{type}` one of the schema's aggregate-root
types (the tenant root and its access record excepted), a loaded graph that matches no loaded-graph
template of its tenant with `{type}` `content`, or a loaded graph the registry already assigns to
another aggregate; in the last case it SHALL refuse before anything is written. Under a flat part template, a request body SHALL be refused with `InvalidBody`
when it names a subject other than the root that is not a part this aggregate already stores (new
parts arrive as blank nodes and are minted); where the part template nests parts under `{root}`, as
the default does, any subject under the root's IRI SHALL be accepted, as today. An API path id that
cannot be an id of the policy SHALL answer 404.

#### Scenario: a hand-made IRI
- **WHEN** an aggregate `http://mwb.meaningfy.ws/p4x8k2m/files/1` is committed under the policy above
- **THEN** the session raises `InvalidIri` and nothing is written

#### Scenario: a loaded graph of another aggregate
- **GIVEN** a loaded graph registered to aggregate A
- **WHEN** aggregate B is committed naming that graph in its loaded graphs
- **THEN** the session raises `InvalidIri` and nothing is written

#### Scenario: an aggregate IRI with a part's type
- **GIVEN** `Term` is an owned class, not an aggregate root
- **WHEN** an aggregate `http://mwb.meaningfy.ws/p4x8k2m/term/a8f3k29dm4x1q` is committed
- **THEN** the session raises `InvalidIri` and nothing is written

#### Scenario: a body that names another aggregate's part
- **GIVEN** aggregate A stores part `http://mwb.meaningfy.ws/p4x8k2m/term/a8f3k29dm4x1q`
- **WHEN** aggregate B is replaced with a body that states triples about that part
- **THEN** the replace is refused with `InvalidBody` and B is unchanged

#### Scenario: a path id of the wrong form
- **WHEN** `GET /projects/P4X8K2M` is requested under a policy of lowercase 7-character tenant ids
- **THEN** the answer is 404 and the store is not queried

### Requirement: Ownership does not depend on IRI nesting

The toolkit SHALL decide which aggregate a subject or a loaded graph belongs to from the
aggregate's graph and the tenant registry, never from one IRI being a prefix of another.

#### Scenario: a listing of aggregates with flat parts
- **GIVEN** two `OntologyFile` aggregates with flat owned parts
- **WHEN** they are listed
- **THEN** each item carries exactly its own parts

### Requirement: Ids are random, short when configured, and never reserved

Ids SHALL be drawn with `secrets` from the configured alphabet (a subset of `[a-z0-9]`) and length,
or be a UUIDv4 when so configured. A minted id SHALL never equal a literal word of a template, an
`rp_iri_type` value, `content`, or the deployment slug. A minted tenant id that an access record
already uses, or whose database name already exists, SHALL be re-drawn.

#### Scenario: a tenant id clash
- **GIVEN** an id source that returns an id already in use, then a free one
- **WHEN** a tenant is created
- **THEN** the create succeeds with the free id

#### Scenario: a reserved id
- **GIVEN** an id source that first returns `project`
- **WHEN** a tenant id of 7 characters is minted under a policy whose tenant template contains `project`
- **THEN** that id is discarded and another is drawn

### Requirement: The policy is fixed once a deployment has data

The service SHALL record its IRI policy in the system database at first start, and SHALL refuse to
start, naming the differing fields, when the configured policy differs from the recorded one. A
system database that has access records but no recorded policy SHALL be taken to hold the default
policy.

#### Scenario: a changed template
- **GIVEN** a deployment started once with object ids of 13 characters
- **WHEN** it is started with object ids of 12 characters
- **THEN** start-up fails naming `object_id.length`, and nothing is minted

#### Scenario: an upgrade of a deployment with data
- **GIVEN** a system database with access records and no recorded policy
- **WHEN** the service starts with a non-default policy
- **THEN** start-up fails, saying the stored data follows the default policy

### Requirement: Policies are checked when settings are made

`ServiceSettings` SHALL refuse a policy whose template uses a variable not allowed for its kind,
whose tenant, aggregate, part, loaded-graph or principal template does not end in its id variable,
whose access, meta or registry template contains neither `{tenant}` nor `{tenant_id}`, whose
aggregate template contains neither `{tenant}` nor `{tenant_id}`, whose part or loaded-graph template
contains none of `{tenant}`, `{tenant_id}` and `{root}`, or that contains a character outside
`[a-z0-9/:.-]` around its variables. Two rules span fields, which the generated models cannot state:
a template that uses `{deployment}` when no deployment slug is set, and a `random` id spec with no
length. They SHALL be refused with `InvalidIri` by `check_iri_policy`, which the service's `Iris` runs when it
is built and which a caller may run on the settings alone. A schema SHALL fail generation when two classes share an `rp_iri_type`
or one equals a reserved word.

#### Scenario: a template without its id
- **WHEN** settings are made with aggregate template `{base}{tenant_id}/{type}`
- **THEN** validation fails naming the aggregate template
