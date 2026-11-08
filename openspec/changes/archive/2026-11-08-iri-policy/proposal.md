<!-- Parents: GitHub issue #26 (and its comment of 2026-11-07); openspec/specs/rp-aggregate-store,
     rp-tenancy, rp-identity, rp-service-api; DEC-29 of the archived soa-python-rdf-orm proposal
     ({root}/graph). Seeds: inputs/issue.md, inputs/seed.md. -->

# EPIC: A configurable IRI policy, independent of API paths

**Golden-thread parent:** GitHub issue #26; the IRI derivations of PD-4, PD-6 and PD-6a
(`rdf_persistence/domain/iris.py`), now made configurable.

## Appetite

**LARGE**, delivered in **two stages** (one change id, one PR per stage). Every place that mints,
checks or parses an IRI changes owner from fixed code to a policy; ownership checks stop relying
on IRI nesting.

## Why

The toolkit mints one fixed shape: UUIDv4 ids (36 characters), every IRI nested under its owner,
and the aggregate segment taken from `rp_path`, which is also the API path. An application with a
persistent URI policy (short opaque ids, flat object IRIs, a deployment segment, identifiers that
survive an API redesign, as public-sector policies require) cannot use the toolkit without
bypassing it. MWB2's first build EPIC is blocked: its identifiers must follow its policy from the
first stored object.

## Solution outline

`ServiceSettings` gains an optional IRI policy (a generated LinkML record) and a `deployment` slug.
The policy gives one template per kind of IRI and an id specification (length and alphabet, or
UUIDv4) for tenant ids and object ids. Templates use `{base}`, `{deployment}`, `{tenant_id}`,
`{type}`, `{id}` and, for principals, `{sub}`; the defaults also use `{tenant}`, `{root}`,
`{tenant_segment}`, `{rp_path}` and `{issuer}` to reproduce today's IRIs exactly, so an application
that sets nothing sees no change.

`{type}` comes from a new class annotation `rp_iri_type` (default: the class name in kebab case),
independent of `rp_path`, which becomes the API path only. Every IRI the toolkit accepts is checked
against the configured templates; ownership of parts and loaded graphs comes from the aggregate's
graph and the registry, never from nesting. Database and bucket names derive from the tenant id.

MWB2's policy, as the worked example the PLAN proves:

| Kind | Template | Example |
|---|---|---|
| Tenant root (portable) | `{base}project/{tenant_id}` | `http://mwb.meaningfy.ws/project/p4x8k2m` |
| Access record (local) | `{base}{deployment}/project/{tenant_id}` | `http://mwb.meaningfy.ws/k3f9a2x/project/p4x8k2m` |
| Meta, registry graphs | `{base}{tenant_id}/meta`, `…/registry` | `http://mwb.meaningfy.ws/p4x8k2m/meta` |
| Aggregate root, owned part | `{base}{tenant_id}/{type}/{id}` | `http://mwb.meaningfy.ws/p4x8k2m/ontology-file/a8f3k29dm4x1q` |
| Loaded graph | `{base}{tenant_id}/{type}/{id}`, `{type}` = `content` | `http://mwb.meaningfy.ws/p4x8k2m/content/z0q7c1m2n8b4v` |
| Aggregate graph | `{root}/graph` (DEC-29, not configurable) | `…/ontology-file/a8f3k29dm4x1q/graph` |
| Principal | `{base}{deployment}/user/{sub}` | `http://mwb.meaningfy.ws/k3f9a2x/user/2840…` |

**Stage 1** (unblocks the consumer's first stored objects): the policy model, the annotation, id
generation, the templates for tenants, aggregate roots, owned parts and loaded graphs, their checks,
path-to-IRI mapping in the API, and resource names. **Stage 2**: the access record, meta, registry
and principal templates, and the policy guard.

## Key decisions

- **DEC-1**: The policy is a generated LinkML record (`IriPolicy`, `IdSpec`) on `ServiceSettings`,
  optional, defaulting to today's IRIs. Source: issue #26; LinkML single source (`AGENTS.md`).
  Rejected: hand-written settings; changing today's default shape.
- **DEC-2**: One template per kind of IRI. The templates of things the API addresses (tenant,
  aggregate root, owned part, loaded graph, principal) end in their own id variable, so the API keeps
  reading the path id as the last segment; the access, meta and registry templates contain
  `{tenant}` or `{tenant_id}`, so the tenant can be read back from them. Source: issue #26 and its
  comment. Rejected: a single object template with a nesting switch.
- **DEC-3**: `{type}` comes from the class annotation `rp_iri_type`, default the kebab-case class
  name; `rp_path` is the API path only. Source: issue #26. Rejected: keeping `rp_path` as the IRI
  segment.
- **DEC-4**: Ids come from `secrets` over the configured alphabet, a subset of `[a-z0-9]`. A minted
  tenant id is checked for a clash in the system database and re-drawn; no id may equal a literal
  word of a template, a `{type}` value or the deployment slug. Source: issue #26.
- **DEC-5**: The aggregate graph stays `{root}/graph` and skolem IRIs stay under the graph.
  Source: DEC-29 of `soa-python-rdf-orm`; issue #26.
- **DEC-6**: The policy is recorded in the system database at first start; a later start with a
  different policy refuses to start and names the difference. Source: developer, 2026-11-08
  (`inputs/seed.md` Q1). Rejected: documentation only.
- **DEC-7**: One EPIC, two stages, one PR per stage. Source: developer, 2026-11-08 (Q2).
- **DEC-8**: Problem types and the JSON-LD context stay under `ServiceSettings.base`, which does not
  contain the deployment slug once `{deployment}` is its own setting. Source: the issue's comment
  (`{base}` has no deployment). Rejected: a separate `vocabulary_base`.
- **DEC-9**: The toolkit's own principal stays `{base}toolkit`, and the recorded policy lives beside
  it. They name the software, not a deployment's data, and the system database is already one per
  deployment. The issue's "system objects with `{deployment}`" are the access records and
  principals, which the policy covers. Rejected: a template for toolkit-owned IRIs.

## Rabbit-holes

- A template language. Templates are plain `str.format` placeholders; no conditionals, no
  per-class templates.
- Migrating stored data between policies. The guard refuses; nothing rewrites IRIs.
- Ambiguity between templates. Checks fill the tenant's known values first and match only the
  remaining variables, so a check is a match against one tenant's templates, not a global parse.

## No-gos

- Attaching an existing tenant database to another deployment (named by the issue as later work;
  this EPIC only makes the split possible).
- Signing content (the issue's "later" note).
- Changing the default IRIs, the aggregate graph rule or the skolem IRIs.
- Rewriting the IRIs of stored data, or any migration tool.
- Per-class or per-tenant policies.

---

## What Changes

- `rdf_persistence/model/service/rp_service.yaml`: `IriPolicy`, `IdSpec`, `ServiceSettings.iri_policy`
  and `ServiceSettings.deployment`; `rdf_persistence/model/rp_core.yaml`: `rp_iri_type` in the
  `RpAnnotation` enum, and `rp_path` described as the API path only.
- `rdf_persistence/domain/iris.py`: minting, checking and parsing driven by the policy; today's
  functions kept for the default policy.
- `services/tenancy.py`, `aggregates.py`, `documents.py`, `mapper.py`, `session.py`, `access.py`,
  `listing.py`: mint and check through the policy; ownership from graphs, not nesting. The
  listing query also returns which graph each subject came from.
- `entrypoints/kit.py`, `auth.py`: path ids map to IRIs through the policy.
- `adapters/jwks.py`: the principal IRI through the policy (stage 2); `testkit/fakes.py`
  (`fake_session`) accepts a policy.
- A generation check: `rp_iri_type` values are unique and are not reserved words.
- As delivered (stage 2): `services/iri_policy_guard.py`, run by `entrypoints/service.py` before
  the sweep; the record is kept through the `Store` port (PD-13). **BREAKING:** the `TokenVerifier`
  port exposes `iris`, checked by `install_service` against the settings (PD-14c).
- Docs: `howto/adopt.adoc` (step 3, tenancy), `architecture/index.adoc`, a worked policy example.

## Capabilities

### New Capabilities

- `rp-iri-policy`: how the toolkit mints, checks and maps every IRI under a configured policy.

### Modified Capabilities

None of the existing requirements change text: their IRIs are "derived by one function", which
stays true. `rp-iri-policy` states the new rules.

## Impact

- Public API: new settings and annotation; `mint_aggregate_iri` and `new_part` keep working for the
  default policy and gain policy-aware forms.
- Every stored IRI of an application that sets a policy follows it; applications that set none
  are unchanged.
- No new dependency.
