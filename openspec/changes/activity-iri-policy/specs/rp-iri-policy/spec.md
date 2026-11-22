## MODIFIED Requirements

### Requirement: Without a policy, IRIs are today's

When `ServiceSettings` sets no `iri_policy`, the toolkit SHALL mint and accept exactly the IRIs and
resource names it minted before this capability: `{base}{tenant_segment}/{uuid4}` for a tenant,
`{tenant}/{rp_path}/{uuid4}` for an aggregate root, `{root}/parts/{uuid4}` for an owned part,
`{root}/content/{uuid4}` for a loaded graph, `{tenant}/access`, `{tenant}/meta`,
`{tenant}/registry`, `{tenant}/provenance`, `{issuer}/users/{sub}` for a principal, `urn:uuid:{uuid4}`
for an activity, and `{prefix}-t-{uuid hex}` for the tenant's database and bucket.

#### Scenario: an application that sets nothing
- **GIVEN** settings without `iri_policy`
- **WHEN** a tenant, an aggregate, an owned part and a loaded graph are minted
- **THEN** each IRI has today's shape, and the existing IRI tests pass unchanged, with one change:
  the access record's graph is no longer an aggregate graph (it stays a valid grant target)

#### Scenario: an activity under the default policy
- **GIVEN** settings without `iri_policy`
- **WHEN** a book is committed serving a command whose id is `urn:uuid:` and a UUID
- **THEN** the recorded activity's IRI is that id

## ADDED Requirements

### Requirement: Activities follow the activity template

The IRI policy SHALL have an `activity_template` (default `urn:uuid:{id}`) using only `{base}`,
`{deployment}`, `{tenant}`, `{tenant_id}` and `{id}` and ending in `{id}`; a template other than
the default SHALL hold `{tenant}` or `{tenant_id}`, and settings with any other SHALL be refused
naming `activity_template`. `{id}` SHALL be the
activity's UUIDv4 in canonical form. A command's id SHALL still be `urn:uuid:` and a UUID; the
session that commits SHALL record the activity under the template, for its tenant or the
application, with the same UUID, and every IRI the toolkit hands on for that activity (to
`on_commit`, the message bus's observers, the relay, transition and comment reads, and
`Session.activity_iri`) SHALL be the recorded one. A follower's `Last-Event-ID` SHALL be resumed
only when it is an activity IRI the policy mints for the followed tenant. The template SHALL be part
of the recorded policy and of a dump's manifest; a record or manifest without it SHALL read as the
default.

#### Scenario: a commit under an activity template
- **GIVEN** an activity template `{tenant}/activity/{id}` and tenant `https://ex.org/projects/p4x8k2m`
- **WHEN** a book is committed serving a command with id `urn:uuid:7a1e1d6e-2f0b-4c57-9a52-2f2f5d1f6a10`
- **THEN** the activity is recorded as
  `https://ex.org/projects/p4x8k2m/activity/7a1e1d6e-2f0b-4c57-9a52-2f2f5d1f6a10`, and no
  `urn:uuid:` IRI is stored in the tenant database

#### Scenario: transitions and comments still find their activity
- **GIVEN** that template
- **WHEN** a book is moved with a comment and another comment is posted on it
- **THEN** the book's transitions and the comment's activity are read back with IRIs under the
  tenant

#### Scenario: resuming a stream under the template
- **GIVEN** that template and a follower whose stream ended after activity A
- **WHEN** it reconnects with `Last-Event-ID` A's recorded IRI
- **THEN** it receives the later events once; with `urn:uuid:` and A's UUID it is reset

#### Scenario: a changed activity template
- **GIVEN** a deployment started once with the default activity template
- **WHEN** it is started with `{tenant}/activity/{id}`
- **THEN** start-up fails naming `activity_template`, and nothing is minted

#### Scenario: a policy recorded before the activity template
- **GIVEN** a system database whose recorded policy has no `activity_template`
- **WHEN** the service starts with the default activity template
- **THEN** the start-up check passes

#### Scenario: a restored tenant keeps its activities
- **GIVEN** a dump of a tenant made under `{tenant}/activity/{id}`
- **WHEN** it is restored to a new tenant id
- **THEN** each restored activity's IRI is under the new tenant, with the same UUID

### Requirement: The activity template is checked

Building `Iris` SHALL refuse with `InvalidIri`, naming `activity_template`, an activity template
whose IRI is not absolute or holds the tenant id without starting with the base. An IRI the
activity template mints for a tenant SHALL never be accepted as an aggregate or loaded graph of
that tenant. Installing the service SHALL refuse a schema with an aggregate root whose IRIs the
activity template would also mint. The default template's words SHALL NOT be reserved ids.

#### Scenario: a tenant-less activity template
- **WHEN** settings are made with activity template `{base}activity/{id}`
- **THEN** validation fails naming `activity_template`

#### Scenario: an activity template that a restore cannot move
- **WHEN** an `Iris` is built with activity template `urn:x:{tenant_id}:{id}`
- **THEN** it fails with `InvalidIri` naming `activity_template`

#### Scenario: an aggregate path inside the activity template
- **GIVEN** activity template `{tenant}/activity/{id}`, UUID object ids and an aggregate root
  whose `rp_path` is `activity`
- **WHEN** the service is installed
- **THEN** installation fails with `InvalidIri` naming the class's type and `activity_template`

#### Scenario: a hand-made aggregate at an activity IRI
- **GIVEN** activity template `{tenant}/activity/{id}`
- **WHEN** an aggregate `<tenant>/activity/<uuid>` is committed
- **THEN** the session raises `InvalidIri` and nothing is written
