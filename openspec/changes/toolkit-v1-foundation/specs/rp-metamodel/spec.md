Capability: rp-metamodel. Source: EPIC `toolkit-v1-foundation`; architecture
`generation.adoc#revision` (D-6, D-7), `access-control.adoc` (D-4, D-5).

## ADDED Requirements

### Requirement: The metamodel ships as separate modules

The toolkit SHALL ship its metamodel as the LinkML modules `rp_core`, `rp_annotations`,
`rp_provenance`, `rp_access`, `rp_tenancy` and `rp_files`, plus `rp.yaml`, which imports them all.
An application SHALL be able to import `rp.yaml` or only the modules it uses.

#### Scenario: an application imports only what it uses
- **WHEN** an application schema imports `rp_core` and `rp_annotations` only
- **THEN** generation succeeds and no access, tenancy or file class appears in its output

### Requirement: Instances of aggregate roots and owned classes are described

Every aggregate root and every owned class SHALL include the `Described` mixin, so its instances
carry an IRI, a label (`skos:prefLabel`) and, on roots, a description (`dcterms:description`). An
owned class MAY opt out of the label with the annotation `rp_unlabelled: true`.

#### Scenario: an instance without a label is refused
- **WHEN** a `Book` instance without a label is validated against the generated shapes
- **THEN** validation fails and names the missing `skos:prefLabel`

#### Scenario: an owned value class opts out
- **WHEN** the owned class `Chapter` is annotated `rp_unlabelled: true`
- **THEN** a chapter without a label validates

### Requirement: Write tracking is stated about the graph

The session SHALL write `dcterms:created`, `dcterms:modified` and `dcterms:creator` of each commit
about the aggregate's graph IRI, never about the root entity. PROV-O derivation slots
(`Provenanced`) SHALL be written by the application only.

#### Scenario: a commit records who and when
- **WHEN** a principal commits a new aggregate
- **THEN** its graph IRI carries `dcterms:created` and `dcterms:creator` with that principal's IRI,
  and the root entity carries neither

### Requirement: Access is modelled with an ODRL subset

`rp_access` SHALL model `Policy` (`odrl:Set`), `Permission`, `Prohibition`, `Principal`
(`odrl:Party`, `prov:Agent`), `Role`, `Scope` (levels `system`, `tenant`, `aggregate`), the `Action`
enum (meanings `odrl:read`, `odrl:modify`, `odrl:delete`, extensible) and `RoleDefinition`. A grant
SHALL be a `Permission`.

#### Scenario: a grant is ODRL
- **WHEN** a grant of the role `librarian` in a library tenant is stored
- **THEN** the store holds an `odrl:Permission` with the principal as assignee and the tenant's
  scope as target
