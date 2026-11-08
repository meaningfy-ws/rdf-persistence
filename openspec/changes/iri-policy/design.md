<!-- PLAN (design half). PLAN = this file + tasks.md. -->

> Derives from: EPIC `iri-policy` (proposal.md), GitHub issue #26.

## Context

All IRIs and resource names are derived in `rdf_persistence/domain/iris.py` (PD-4, PD-6, PD-6a of
`toolkit-v1-foundation`). They are minted in `services/tenancy.py` (tenant, access record, resource
names), `services/aggregates.py` (roots), `services/documents.py` and `services/mapper.py` (parts,
`new_part`), `services/session.py` (loaded graphs); checked in `services/session.py` (`_graph`,
`_check_commit`) and `services/access.py` (`is_aggregate_iri`); mapped from API path ids in
`entrypoints/kit.py` (`tenant_iri`) and `entrypoints/auth.py` (`aggregate_iri`); and mapped back to
path ids in `entrypoints/router.py` (`_last_segment`). Two places infer ownership from nesting:
`services/listing.py:_owner` and `services/documents.py:_inside`. The principal IRI is minted in
`adapters/jwks.py`. Problem types live under `base` (`entrypoints/problems.py`).

## Goals / Non-Goals

**Goals:** DEC-1 to DEC-8, staged per DEC-7. **Non-Goals:** the EPIC's No-gos.

## Decisions

- **PD-1 Model.** In `rdf_persistence/model/service/rp_service.yaml`:
  - `IdSpec`: `kind` (enum `uuid4` | `random`), `length` (int, 4 to 32, required for `random`),
    `alphabet` (string, default `0123456789abcdefghijklmnopqrstuvwxyz`, every character in `[a-z0-9]`).
  - `IriPolicy`: `tenant_template`, `access_template`, `meta_template`, `registry_template`,
    `aggregate_template`, `part_template`, `loaded_graph_template`, `principal_template` (strings),
    `tenant_id`, `object_id` (`IdSpec`). Every slot has an `ifabsent` default equal to today's shape
    (table below), so `IriPolicy()` is the default policy.
  - `ServiceSettings.iri_policy` (optional, absent = `IriPolicy()`), `ServiceSettings.deployment`
    (optional, pattern `^[a-z0-9]{1,32}$`).
  - Cross-field checks (template variables, ends-in-id, `{deployment}` needs a slug, alphabet) run
    in the generated model through the existing pydantic-validator generator extension
    (`generation/extensions/pydantic_validators.py`) or a rule the schema can express; where neither
    can, a check function in `domain/iris.py` called once by `install_service`. The implementer
    picks the first that works and records which in this file.
  - Implemented as: the variable sets, the closing id variable, the tenant requirement and the
    literal characters are one `pattern` per template slot in `rp_service.yaml` (generated into the
    pydantic validators, shapes and schemas); the alphabet is a pattern and the length a 4 to 32
    range. Only `{deployment}` without a slug and `random` without a length span fields, so
    `check_iri_policy(settings)` in `domain/iris.py` raises `InvalidIri` for them; the `Iris`
    constructor (2.1) calls it, so a service with such settings refuses to be built (leader's
    decision, task 1.1: the generated validators express presence rules only). An absent `tenant_id` or `object_id` means `IdSpec(kind: uuid4)`
    (an object-valued slot has no `ifabsent`).
- **PD-2 Defaults.**

  | Template | Default | Allowed variables |
  |---|---|---|
  | tenant | `{base}{tenant_segment}/{tenant_id}` | base, deployment, tenant_segment, tenant_id |
  | access | `{tenant}/access` | base, deployment, tenant, tenant_id |
  | meta | `{tenant}/meta` | base, deployment, tenant, tenant_id |
  | registry | `{tenant}/registry` | base, deployment, tenant, tenant_id |
  | aggregate | `{tenant}/{rp_path}/{id}` | base, deployment, tenant, tenant_id, type, rp_path, id |
  | part | `{root}/parts/{id}` | base, deployment, tenant, tenant_id, root, type, id |
  | loaded graph | `{root}/content/{id}` | base, deployment, tenant, tenant_id, root, type, id |
  | principal | `{issuer}/users/{sub}` | base, deployment, issuer, sub |

  Default `IdSpec` for both ids: `kind: uuid4`. `{sub}` is percent-encoded as today.
  The access, meta and registry templates contain `{tenant}` or `{tenant_id}`; every other
  template ends in its id variable (`{tenant_id}`, `{id}`, `{sub}`) (DEC-2).
- **PD-3 Domain API.** A frozen domain class `Iris` in `domain/iris.py`, built once from
  `(settings, iri_policy)`, with `mint_tenant()`, `tenant(tenant_id)`, `tenant_id_of(tenant_iri)`,
  `access(tenant)`, `meta(tenant)`, `registry(tenant)`, `mint_aggregate(tenant, cls_type, rp_path)`,
  `aggregate(tenant, cls_type, rp_path, id)`, `mint_part(tenant, root, cls_type)`,
  `mint_loaded_graph(tenant, root)`, `is_aggregate(tenant, iri)`, `is_loaded_graph(tenant, iri)`,
  `principal(issuer, sub)`, `resource_name(tenant)`, `is_aggregate_graph(tenant, iri)`. `Iris` is
  built from the settings **and the schema**: it holds the set of aggregate-root types and the set
  of owned-class types (from `rp_iri_type`), which PD-4 needs. Today's module functions stay as
  thin calls on the default `Iris`, so existing callers and the public `mint_aggregate_iri` /
  `new_part` keep working (`new_part` gains an optional `iris` and `tenant` for non-default
  policies). `Iris.is_aggregate(tenant, iri)` keeps today's two extra cases of `is_aggregate_iri`
  (`iris.py:105`): the tenant root itself and its access record (the access template filled), on
  which the system-database session relies.
- **PD-3c Access rules a consumer built (lead's decision before task 3.4).** `install_service`
  accepts `rules` as a path or as an `AccessRules` the consumer built, which holds the default
  `Iris`. The kit builds its one `Iris` (settings plus `iri_types(view)`) and rebinds the rules to
  it: `AccessRules.with_iris(iris)` answers a new `AccessRules` with the same role permits. So every
  service the kit wires, rules included, uses one policy; a consumer never has to pass an `Iris`.
  The route's `{type}` comes from the class served at `rp_path` (`iri_type_of`).
- **PD-3b The schema reaches `Iris` as types** (lead's decision before task 2.1). `domain` imports no
  LinkML, so `Iris` takes `root_types` and `owned_types` (frozen sets of `{type}` values), not the
  schema. One services function, `iri_types(view)` in `services/schema_structure.py`, computes them;
  `iri_type_of(cls)` (the annotation, else the kebab-case class name) moves there from
  `generation/checks/hard.py`, which imports it, so the generation check and the minted IRIs use one
  rule.
- **PD-3a Who receives `Iris`.** `install_service` builds one and hands it to tenancy, aggregates,
  documents, session factory and access rules. Classes a consumer builds itself take it as an
  optional constructor argument defaulting to the default `Iris`: `Session`, `JwksTokenVerifier`
  (`adapters/jwks.py`, for `principal`), and `fake_session` in `testkit/fakes.py`.
- **PD-4 Matching.** A check fills the known variables (base, deployment, tenant, tenant_id,
  root) and compiles the rest into a regex. `{type}` is an alternation of the allowed types only:
  the aggregate-root types for the aggregate template, the owned-class types for the part
  template, `content` for the loaded-graph template. An id becomes its `IdSpec` pattern
  (`[{alphabet}]{length}` or the canonical UUID pattern), `{rp_path}` the `url_segment` pattern.
  Literal text is `re.escape`d. Patterns are compiled once per `Iris` with the tenant parts as
  named groups and compared against the tenant afterwards, so nothing is compiled per request.
- **PD-5 Ids.** `secrets.choice` per character, or `uuid4()`. A drawn id equal to a reserved word
  (literal path words of all templates, every `rp_iri_type` of the schema, `content`, the
  deployment slug) is re-drawn. Tenant ids: `Tenancy.create` re-draws a candidate whose access
  record exists in the system database **or** whose resource name `Store.list_datasets()` already
  lists (an orphan of an interrupted create), at most 5 draws, then fails with `PersistenceError`
  ("no free tenant id"). Two concurrent creates drawing the same 7-character id between check and
  create (1 in 36⁷ ≈ 7.8·10¹⁰ per pair) are not guarded; if it happens, the second
  `create_dataset` fails and the create returns an error, leaving nothing behind the sweep cannot
  clean. Object ids are not checked: at 13 characters over 36 symbols (≈ 67 bits), a million
  objects in a tenant clash with probability ≈ 3·10⁻⁹.
- **PD-6 Resource names.** `{prefix}-t-{tenant_id without hyphens}`: a UUIDv4 gives today's hex.
  With `prefix` at most 20 characters and `IdSpec.length` at most 32, a name is at most 55
  characters, inside the 63-character bucket limit; no runtime check is needed.
- **PD-7 Ownership.**
  - *Listing.* `_LISTING` (`services/listing.py:71`) constructs plain triples, so the graph is lost.
    It gains one triple per subject, `?s rp:listedIn ?graph`, in the CONSTRUCT template (a toolkit
    vocabulary term added to `rp_core.yaml`); `items_of` groups each triple by its subject's
    `listedIn` graph (`root_of_graph`) and drops the `listedIn` triples. `_owner` is deleted. A
    subject is in exactly one aggregate graph because parts are unique to their aggregate (next
    rule).
  - *Parts in a body.* Two rules, chosen by the part template:
    - **Nested** (the part template starts with `{root}/`, as the default does): `documents._inside`
      stays as it is, a subject under the root's IRI is accepted. Nothing changes for applications
      without a policy, including clients that name their own parts under the root on a replace.
    - **Flat** (any other part template): `Documents.parse` (`documents.py:162`, no session) accepts
      only the root and parts it mints now for blank nodes. Every other subject IRI is "named by the
      body": `parse` and `Aggregates._triples` (`aggregates.py:92`) also return the set of these
      named subjects (a `(graph, named)` pair, local to the services layer), because after
      `_triples` a minted part and a client-named part look alike. `Aggregates.replace` (`aggregates.py:76`), right after
      `session.get_graph(iri)` reads the stored aggregate, refuses with `InvalidBody` any named
      subject that is not a subject of the stored graph, before `replace_graph`. `Aggregates.create`
      refuses any named subject at once (nothing is stored yet).
  - *Loaded graphs.* `load_graph` (`session.py:399`) writes an unregistered graph; the commit that
    names it registers it. `_check_commit` therefore asks the registry, in one `ASK` before the
    update, whether any **other** aggregate owns the graph, and refuses if so. A race between two
    commits naming one freshly loaded graph needs a caller who forges the IRI of a graph another
    request just loaded, inside one tenant where it already has write access; it is accepted and
    written down here.
- **PD-7a The type of a new part (lead's decision before task 3.2).** A blank node `Documents`
  names as a part takes its `{type}` from its `rdf:type`, mapped to its class through the schema
  (`iri_type_of`). When the part template contains `{type}` and the node has no `rdf:type`, or one
  that is not an owned class of the schema, the body is refused with `InvalidBody` naming the
  type, never `InvalidIri`: the body is at fault, so the answer is 422. A template without `{type}`
  (the default) does not read the type, so nothing changes for today's bodies. Until task 3.4 wires
  one `Iris`, `Aggregates`, `Documents`, `Session` and `new_part` take an optional `iris`
  defaulting to the default-policy `Iris` the module shims use, which mints today's IRIs.
- **PD-7b `new_part` and `rp_iri_type` (lead's decision, found in task 3.2).** The generated
  pydantic classes carry no LinkML metadata (`linkml_meta = None`), so `new_part(cls, …)` cannot
  read a class's `rp_iri_type`; it uses the kebab-case class name, the default `{type}`. Under a
  template with `{type}`, a part class whose `rp_iri_type` differs is refused by `Iris` with
  `InvalidIri` (never a wrong IRI), and the docstring and `adopt.adoc` say so. Bodies through
  `Documents` read the annotation from the schema and are not affected. Upgrade when the generator
  emits class metadata, or when a consumer needs `rp_iri_type` on a part built in code.
- **PD-8 `rp_iri_type`.** A new value of the `RpAnnotation` enum in `rdf_persistence/model/rp_core.yaml`
  (beside `rp_path`, `rp_core.yaml:149`), whose `rp_path` description becomes "its path segment in
  the API" (no longer "and in its IRIs"). The value follows the `url_segment` pattern, as `rp_path`
  does. A generation check in `generation/checks/hard.py` fails on two classes with one type, or a
  type equal to `content`, `graph`, `parts`, `access`, `meta`, `registry`.
- **PD-9 Policy guard (stage 2).** The policy is stored as an `IriPolicy` instance in the system
  database, in the graph of `{base}toolkit/iri-policy` (beside the toolkit principal
  `{base}toolkit`), written through the toolkit session at start-up after the sweep. On start: no
  record and no access records → write it; no record but access records → the stored data is the
  default policy, so refuse unless the configured policy is the default, else write it; a record →
  compare field by field, refuse naming the differing fields (`ServiceUnavailable`-class start-up
  error, logged with `step: iri-policy`).
- **PD-10 Access record lookup.** `TenantAccess` has no `tenant` slot (`rp_tenancy.yaml:45`), and
  adding one would leave stored records without it. `tenant_iri_of_access` becomes
  `Iris.tenant_of_access(iri)`: it matches the access template (which contains `{tenant}` or
  `{tenant_id}`, DEC-2), takes the tenant or its id, and fills the tenant template. Stored records
  need no change. The `database_name` description in `rp_tenancy.yaml` ("UUID in hexadecimal")
  becomes "the tenant id".
- **PD-10a `database_name` pattern (gap found in task 3.1).** The slot's pattern
  `-t-[0-9a-f]{32}$` refused every name a non-UUID policy makes (`mwb-t-4fe0bvg`), so a consumer's
  tenant could not be stored. The pattern becomes `^[a-z][a-z0-9]{0,19}-t-[a-z0-9]{4,32}$`: the
  union of every `IdSpec` (length 4 to 32 over `[a-z0-9]`, PD-6) and the UUID hex of the default.
  The description change of PD-10 moves with it into task 3.1. Stored names all still match.
- **PD-11 Grant targets.** `access._validate_ends` (`services/access.py:205`) calls
  `Iris.is_aggregate_graph`, which is `root_of_graph` followed by the aggregate match of PD-4.

## Algorithm / approach

Mint an aggregate under MWB2's policy:

```python
iris = Iris(settings)               # base http://mwb.meaningfy.ws/, deployment k3f9a2x
iris.mint_aggregate("http://mwb.meaningfy.ws/project/p4x8k2m", "ontology-file", "files")
# tenant_id = iris.tenant_id_of(tenant)  -> "p4x8k2m"  (matched against the tenant template)
# id = draw(object_id)                   -> "a8f3k29dm4x1q"
# -> http://mwb.meaningfy.ws/p4x8k2m/ontology-file/a8f3k29dm4x1q
```

API read `GET /projects/p4x8k2m/files/a8f3k29dm4x1q`: `kit.tenant_iri("p4x8k2m")` checks the id
against `tenant_id` (else 404) and fills the tenant template; `auth.aggregate_access` fills the
aggregate template with the route's class type and the id (else 404). Answers carry `id` = IRI; the
router's `_last_segment` gives the path id back, because every template ends in its id (PD-2).

Idempotency: minting is not idempotent (random), as today; a retried create mints a new object.
The guard's first write is idempotent: writing an equal record twice changes nothing.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| `iri.startswith(tenant + "/")` | `iris.is_aggregate(tenant, iri)` | flat objects are not under the tenant IRI |
| Walk IRI parents to find a root | read the graph that holds the subject | PD-7 |
| `random` or `uuid` for short ids | `secrets` | ids are guessable otherwise |
| A per-call `Iris(settings)` | one `Iris` built in the composition root and passed in | templates compile once |
| Hand-write `IriPolicy` | LinkML slot + `make generate` | single source |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Template invalid (variable, end, characters) | settings validation | `ValidationError` naming the template |
| `{deployment}` used, no slug | `check_iri_policy`, when `Iris` is built | `InvalidIri` naming the template and `deployment` |
| `random` id without `length` | `check_iri_policy`, when `Iris` is built | `InvalidIri` naming the id spec |
| `IdSpec.length` outside 4 to 32 | settings validation | `ValidationError` naming the field |
| Tenant id clash | access record or dataset exists for candidate | re-draw, at most 5, then `PersistenceError` |
| Same id drawn by two concurrent creates | second `create_dataset` fails | create fails; sweep cleans (PD-5) |
| Aggregate IRI with a part's or unknown type | `{type}` alternation (PD-4) | `InvalidIri`, nothing sent |
| Body names a foreign subject | part rule (PD-7) | `InvalidBody`, nothing written |
| Reserved id drawn | membership in the reserved set | re-draw |
| Aggregate IRI matches no template | `_check_commit` | `InvalidIri`, nothing sent |
| Loaded graph owned by another aggregate | registry read in commit | `InvalidIri`, nothing written |
| Path id of the wrong form | `IdSpec` pattern | 404, store not queried |
| Policy differs from recorded | start-up guard | refuse to start, naming fields |
| Two classes, one `rp_iri_type` | generation check | generation fails, naming both |

## Risks / Trade-offs

- [Wide change across services] → stage 1 keeps the module functions as default-policy shims, so
  each caller moves in its own task with its tests green; gitnexus impact before each task.
- [Flat parts make a replace stricter: a client may no longer add a part with an IRI it chose]
  → only under a flat part template, which no application uses yet; the default keeps the nested
  rule (PD-7). Tested by "a body that names another aggregate's part".
- [Listing ownership rewrite touches a hot path] → the listing's existing feature tests plus a flat
  policy variant of them.
- [Templates that overlap, e.g. aggregate and part both `{base}{tenant_id}/{type}/{id}`] → allowed:
  the `{type}` alternations of PD-4 are disjoint (root types, owned types, `content`; the
  generation check of PD-8 keeps types unique), so one IRI matches at most one kind.

## Open Questions

None blocking. The developer may overturn any leader's choice listed in `inputs/seed.md`.
