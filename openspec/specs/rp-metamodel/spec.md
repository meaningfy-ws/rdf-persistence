# rp-metamodel Specification

## Purpose
TBD - created by archiving change toolkit-v1-foundation. Update Purpose after archive.
## Requirements
### Requirement: The metamodel ships as separate modules

The toolkit SHALL ship its metamodel as the LinkML modules `rp_core`, `rp_annotations`,
`rp_provenance`, `rp_access`, `rp_tenancy` and `rp_files`, plus `rp.yaml`, which imports them all.
An application SHALL be able to import `rp.yaml` or only the modules it uses.

#### Scenario: an application imports only what it uses
- **WHEN** an application schema imports `rp_core` and `rp_annotations` only
- **THEN** generation succeeds and no access, tenancy or file class appears in its output

### Requirement: Instances of aggregate roots and owned classes are described

Every aggregate root and every owned class SHALL include the `Described` mixin, so its instances
carry an IRI, a label (`skos:prefLabel`) and MAY carry a description (`dcterms:description`). An
owned class MAY opt out of the label with the annotation `rp_unlabelled: true`. Every generated
artefact SHALL treat the description as optional, on roots and on their `is_a` subclasses alike.

#### Scenario: an instance without a label is refused
- **WHEN** a `Book` instance without a label is validated against the generated shapes
- **THEN** validation fails and names the missing `skos:prefLabel`

#### Scenario: an owned value class opts out
- **WHEN** the owned class `Chapter` is annotated `rp_unlabelled: true`
- **THEN** a chapter without a label validates

#### Scenario: a root and its subclass need no description
- **GIVEN** an abstract class mixing in `AggregateRoot` and `Described`, and a served subclass of it by `is_a`
- **WHEN** `rp-generate` runs and both generated classes are built with only an id and a label
- **THEN** both validate, and the JSON Schema of each lists only `id` and `label` as required

### Requirement: Write tracking is stated about the graph

The session SHALL write `dcterms:created`, `dcterms:modified` and `dcterms:creator` of each commit
about the aggregate's graph IRI, never about the root entity. PROV-O derivation slots
(`Provenanced`) SHALL be written by the application only.

#### Scenario: a commit records who and when
- **WHEN** a principal commits a new aggregate
- **THEN** its graph IRI carries `dcterms:created` and `dcterms:creator` with that principal's IRI,
  and the root entity carries neither

### Requirement: Access is modelled with an ODRL subset

`rp_access` SHALL model `Policy` (`odrl:Set`), `Permission`, `Prohibition`, the `Action` enum (meanings `odrl:read`, `odrl:modify`, `odrl:delete`
and `rp:administer`, extensible) and `RoleDefinition`, using `rp_core`'s `Principal` (`prov:Agent`, `odrl:Party`) as assignee. A
grant SHALL be a `Permission` whose target
is a tenant IRI or an aggregate's graph IRI; the system level SHALL come only from global roles in
the token.

#### Scenario: a grant is ODRL
- **WHEN** a grant of the role `librarian` in a library tenant is stored
- **THEN** the store holds an `odrl:Permission` with the principal as assignee, the tenant's IRI as
  target and `rp:role` `librarian`

