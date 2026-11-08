<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

Copied verbatim from GitHub on 2026-11-08.

# Issue #26: Configurable IRI policy, independent of API paths (short opaque ids, flat object IRIs, deployment segment)

https://github.com/meaningfy-ws/rdf-persistence/issues/26

## Summary
The toolkit hard-codes one IRI shape for everything it mints, uses random UUIDv4 local names (36 characters), nests every IRI under its owner, and derives the IRI segment from `rp_path`, which is also the API path. An application with a persistent URI policy of its own (as public-sector URI policies require: short opaque identifiers, a fixed shape independent of the API, a deployment segment) cannot use the toolkit without a workaround. Please make the IRI policy configurable, and decouple IRIs from API paths.

## Context
- Consumer: MWB2 (mapping-workbench-v2), architecture revision `architecture-v1-revision` (ADR-013, URI policy), developer decision of 2026-11-07.
- The consumer's policy, as an example of what must be expressible (all segments lowercase `[a-z0-9]`):
  - base `http://mwb.meaningfy.ws/`, then a 7-character **deployment slug** fixed per deployment;
  - a **tenant** IRI: `{base}{deployment}/{tenant-type}/{tenant-id}` with a 7-character tenant id;
  - every object **inside a tenant** (aggregate roots, owned parts, loaded graphs): `{base}{deployment}/{tenant-id}/{type}/{id}`, flat, with a 13-character id and a `type` segment named after its class; never nested under its owner;
  - the aggregate's graph stays `{root}/graph` (DEC-29), as today;
  - vocabulary and problem types live under a base that is **not** deployment-specific.
- rdf-persistence commit: `e5ca99d` (develop).

## Current behaviour
`rdf_persistence/domain/iris.py`:
```python
mint_tenant_iri(base, tenant_segment)  # {base}{tenant_segment}/{uuid4}
mint_aggregate_iri(tenant_iri, rp_path) # {tenant_iri}/{rp_path}/{uuid4}
mint_part_iri(root_iri)                 # {root_iri}/parts/{uuid4}
loaded_graph_iri(aggregate_iri)         # {aggregate_iri}/content/{uuid4}
```
- The session refuses any aggregate IRI that is not exactly this shape (`InvalidIri`), and a loaded graph not under `{iri}/content/`.
- `rp_path` is both the API path segment and the IRI segment (`howto/adopt.adoc`, step 3: "its path segment in the API and in its IRIs"), so changing the API changes identifiers.
- Problem types are minted under the same `base` as the data (`ServiceSettings.base`).
- Database and bucket names derive from the UUID hex (`{prefix}-t-{uuid hex}`).

## Proposed capability
An `IriPolicy` in `ServiceSettings` (generated record, defaults reproducing today's behaviour so no existing application changes):

```python
IriPolicy(
    base="http://mwb.meaningfy.ws/k3f9a2x/",          # instance data base, deployment slug included
    vocabulary_base="http://mwb.meaningfy.ws/",         # problem types and other deployment-independent terms
    tenant_template="{base}{tenant_type}/{tenant_id}",
    object_template="{base}{tenant_id}/{type}/{id}",    # roots, owned parts, loaded graphs: flat
    tenant_id=IdSpec(length=7, alphabet="0123456789abcdefghijklmnopqrstuvwxyz"),
    object_id=IdSpec(length=13, alphabet="0123456789abcdefghijklmnopqrstuvwxyz"),
)
```
- `type` comes from a new class annotation (e.g. `rp_iri_type: ontology-file`), defaulting to the class name in kebab case; it is **independent of `rp_path`**, which stays the API path only.
- Ids come from `secrets` (cryptographic RNG); a minted tenant id is checked for uniqueness in the system database and re-drawn on a clash (7 characters is short); ids never equal a reserved word (a type segment such as `project`).
- `{root}/graph`, the designated graphs and the access record keep derived IRIs (`{tenant}/meta` or a template), as configured.
- The session's IRI check (`InvalidIri`) validates against the configured templates instead of the fixed shape.
- Database and bucket names derive from the tenant id (already lowercase), e.g. `{prefix}-t-{tenant_id}`.
- The principal IRI template is configurable too (today `{issuer}/users/{sub}`).

Intended use in the consumer's composition root:
```python
settings = ServiceSettings(base=..., prefix="mwb2", tenant_segment="projects",
                           iri_policy=IriPolicy(...), ...)
kit = install_service(app, schema=SCHEMA, generated=generated, settings=settings, ...)
# POST /projects            -> tenant  http://mwb.meaningfy.ws/k3f9a2x/project/p4x8k2m
# POST /projects/{t}/files  -> object  http://mwb.meaningfy.ws/k3f9a2x/p4x8k2m/ontology-file/a8f3k29dm4x1q
```

## Why it belongs in rdf-persistence
IRIs are minted and validated by the toolkit (session, mapper, tenancy, router); an application cannot change them without bypassing the toolkit. A persistent URI policy is a standard requirement of data-centric and public-sector applications, and identifiers must not change when an API is redesigned. Every application on the toolkit would need this.

## Acceptance
- **Given** no `iri_policy`, **when** an application mints tenants, aggregates, parts and loaded graphs, **then** the IRIs are exactly today's.
- **Given** the policy above, **when** a tenant is created, **then** its IRI is `{base}project/{7 chars}` and its database and bucket are named from that id.
- **Given** the policy above, **when** an aggregate, an owned part or a loaded graph is minted, **then** its IRI is `{base}{tenant_id}/{type}/{13 chars}`, flat, and the session accepts it.
- **Given** a class whose `rp_path` changes, **when** new objects are minted, **then** their IRIs do not change shape.
- **Given** an aggregate IRI that matches no configured template, **when** it is committed, **then** the session raises `InvalidIri`.
- **Given** a tenant id clash, **when** a tenant is created, **then** a new id is drawn and the create succeeds.

## Impact on the consumer
Blocks the consumer's first build EPIC: identifiers are persistent, so they must follow the policy from the first stored object.

## Later, not part of this issue
The consumer will later want content signed (an aggregate version signed with a post-quantum signature, e.g. ML-DSA over the canonicalised graph). The policy above keeps ids opaque and independent of content, so signing can be added later without changing identifiers.


## Comment (2026-11-07T22:07:28Z)

Update from the consumer (2026-11-07): the policy example changed so that tenant data is portable between deployments. The capability asked for is the same (configurable templates and id lengths, IRIs independent of API paths); the templates must now also allow:

- **Two IRIs per tenant**: the tenant root (portable, no deployment segment), e.g. `{base}project/{tenant_id}`, and the deployment's tenant access record (local), e.g. `{base}{deployment}/project/{tenant_id}`, instead of today's `{tenant}/access`.
- **Objects inside a tenant without the deployment segment**: `{base}{tenant_id}/{type}/{id}`; designated graphs `{base}{tenant_id}/meta` and `/registry`.
- **System objects with it**: `{base}{deployment}/{type}/{id}`, and principals `{base}{deployment}/user/{sub}`.

So the template variables are `{base}` (no deployment), `{deployment}`, `{tenant_id}`, `{type}`, `{id}`, each template choosing which it uses. Since tenant ids are checked for uniqueness only within one deployment, a later capability (not part of this issue) will be to attach an existing tenant database to a deployment by creating a new access record for it; the split above is what makes that possible.
