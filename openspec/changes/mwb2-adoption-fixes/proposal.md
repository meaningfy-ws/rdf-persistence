<!-- Parents: issues #42 to #51 (filed by mapping-workbench-v2, 2026-11-08/09), serving MWB2
     changes v1-01, v1-03, v1-04 and v1-05 (D-12). Seeds, the developer's answers and the re-shape
     log: inputs/seed.md. -->

# EPIC: Fix what mapping-workbench-v2 met while adopting the toolkit

> Shaped 2026-11-09 from #42–#45 (Q-1 to Q-4). **Re-shaped the same day** to take in #46–#51
> (developer's answer Q-5: one EPIC, delivered in stages); DEC-1 to DEC-4 stand unchanged, DEC-5 to
> DEC-10 added. Log: inputs/seed.md, "Re-shape". PLAN: design.md + tasks.md.

**Golden-thread parents:** `rp-access` (who may do what to a tenant), `rp-tenancy` (the tenant's
label and record), `rp-service-api` (the generic routes and `install_service`), `rp-generation`
(the boundary checks and generated artefacts), `rp-testkit` (the public test surface),
`rp-package-boundaries`, and the adoption guide (`howto/adopt.adoc`).

## Appetite

**LARGE**, four stages, one PR each. Several related capabilities (access, tenancy, service API,
generation, testkit); one behaviour change to an existing route (DEC-1) and new optional
parameters of `install_service`. Existing structure is reused; no new layer or port.

## Why

MWB2 is the first consumer to adopt the toolkit by the book. Its issues fall in three groups:

- **It cannot follow the toolkit's own rules** — #42 no `py.typed`; #45 the adoption guide's
  imports are refused by `assert_public_imports`; #47 no generated TypeScript for the service's
  types; #48 a `technical` module cannot hold the API shapes it is meant for.
- **It cannot express a common access need** — #43 a role that may delete aggregates may delete
  the tenant; #49 no way to enforce a rule on the generic grant, root and label writes; #50 a
  `modify`-only role cannot rename (it cannot read the version); #51 a UI cannot tell what the
  caller may do.
- **Data drifts or cannot be tested** — #44 a rename leaves the root's label stale; #46 a test
  cannot force an id clash without patching internals.

#43, #49 and #50 block MWB2's v1-05 ("projects and members"), and MWB2 will not work around them.

## Solution outline

- **Stage 1 — v1-05 blockers and small fixes (#42–#46, #50).** The wheel ships `py.typed`.
  Deleting a tenant needs `administer`. A tenant has one label, written by the rename to root and
  record. The guard helpers are top-level testkit names and the guide uses only those.
  `install_service` takes an `id_source`. The tenant root's read carries the record's version, so
  any reader can rename with `modify`.
- **Stage 2 — consumer rules on tenant writes (#49).** `install_service` takes grant and root
  validators that run inside the write after the version check; a validator's refusal is a 422,
  and two concurrent writes at one version still give one 409.
- **Stage 3 — API shapes (#47, #48).** Classes of a `technical` module are exempt from the
  ownership rule; `rp-generate` writes the service's wire types as `rp_service.ts`.
- **Stage 4 — permitted actions (#51).** Document reads carry the caller's permitted actions in a
  header; tenant summaries carry them in a slot.

## Key decisions

- **DEC-1**: `DELETE` on a tenant requires `administer` on the tenant. Source: Q-1. Reason: deleting
  the tenant is an act on who may use it at all, like changing its grants; the smallest change.
  **BREAKING** for roles that hold `delete` without `administer`. Rejected: a
  `tenant_delete_action` setting.
- **DEC-2**: `rename` checks the record's version, writes the new label to the root object, then to
  the access record; a `PUT` on the root whose `label` differs from the record's is refused as an
  invalid body. Source: Q-2. Reason: two datasets, no single write; the record is the authority and
  is written last; a retry converges. Rejected: deriving the label when served; `PUT` on the root
  renaming the tenant.
- **DEC-3**: The guard API becomes top-level names of `rdf_persistence.testkit`, loaded lazily
  where the module loads `pyshacl` or `hypothesis`. `assert_public_imports` keeps its rule. Source:
  Q-3. Rejected: an allow-list of testkit modules.
- **DEC-4**: `py.typed` is checked in the built wheel. Source: #42's acceptance.
- **DEC-5**: `GET /{segment}/{t}` also answers the access record's version in a `Record-ETag`
  header; the rename takes it as `If-Match`. Source: Q-6. Reason: the smallest change that lets a
  `modify` role rename; DEC-2 stays. Rejected: one combined label+root edit.
- **DEC-6**: `install_service` takes `grant_validators` and `root_validators` (default none). They
  run in the toolkit's write path after the record or root is read and before the conditional
  write; raising `InvalidBody` refuses the write (422). Grant validators run on every grant-set
  write; root validators on tenant create, root replace and rename. Source: Q-7. Reason: every
  write goes through the check, and the `If-Match` write keeps check-then-write atomic. Rejected:
  unmounting the generic routes.
- **DEC-7**: `install_service` takes `id_source` (default: the cryptographic draw), passed to the
  kit's `Iris`. Source: #46's proposal. Reason: ids are minted only by the toolkit, so only it can
  open the seam.
- **DEC-8**: When a target has `typescript` set, `rp-generate` also writes the service's wire types
  (`rp_service.yaml`) as `rp_service.ts`, exported from `index.ts`. Source: planner, flagged for
  veto. Reason: needs no consumer schema change; making `rp_service` importable would also need the
  Python generator to map a second metamodel folder. Rejected: an importable `rp_service`.
- **DEC-9**: The ownership rule skips classes of modules annotated `module_kind: technical`; they
  are generated as today. Source: #48's proposal. Reason: such classes are never stored.
- **DEC-10**: Reads of a tenant root and of an aggregate answer the caller's permitted actions in
  an `Allowed-Actions` header (from `read, modify, delete, administer`, in that order);
  `TenantSummary` gains an optional multivalued `allowed_actions` slot, filled in the listing.
  Source: Q-8. Reason: the stored document stays free of access data. Rejected: a field in every
  body.

## Rabbit-holes

- **A rename that fails halfway (#44).** No compensation; the record is written last, a retry
  converges.
- **Existing tenants whose root label already differs (#44).** No migration; the next rename repairs
  them.
- **Validators and concurrency (#49).** Atomicity comes from the conditional write that already
  exists; no lock, no transaction across datasets. A root validator on rename sees the root after
  the label change.
- **CORS (#50, #51).** The toolkit sets no CORS headers; a consumer whose web app is on another
  origin exposes `ETag`, `Record-ETag` and `Allowed-Actions` itself. The guide says so.
- **`rp_service.ts` pulls in its imports (#47).** `rp_core.ts`, `rp_access.ts`, `rp_tenancy.ts` are
  already written; the step adds only the files that are missing.

## No-gos

- A configurable delete action, or new actions in the vocabulary.
- Changing what `delete` means for aggregates, or how Prohibitions are scoped.
- Deriving or caching labels at read time; a cross-dataset transaction.
- Unmounting the generic routes (#49 option B); validators on aggregate writes other than the root.
- Making `rp_service` importable by consumer schemas; OpenAPI components for technical classes.
- `allowed_actions` in the stored or framed documents, or on items of aggregate listings.
- Making more testkit modules public by path; exporting helpers the guide does not document.
- Type stubs (`.pyi`) or typing changes beyond the marker.

---

## What Changes

- **Stage 1**: `rdf_persistence/py.typed` and a wheel check (#42). `entrypoints/router.py`: tenant
  `DELETE` gated by `administer` (#43, **BREAKING**: a `delete` Prohibition on a tenant no longer
  stops deleting it; one of `administer` does); the root read answers `Record-ETag` (#50).
  `services/tenancy.py` and `services/aggregates.py`: one label (#44). `testkit/__init__.py` and
  `howto/adopt.adoc` step 6 (#45). `entrypoints/service.py`, `entrypoints/kit.py`: `id_source` (#46).
- **Stage 2**: `install_service`, `ServiceKit`, `Tenancy`, `Aggregates`: grant and root validators
  (#49).
- **Stage 3**: `generation/checks/boundary.py` (#48); `generation/extensions/typescript.py` or its
  step: `rp_service.ts` (#47).
- **Stage 4**: `model/service/rp_service.yaml` (`allowed_actions` on `TenantSummary`, regenerated);
  the read routes and the listing; OpenAPI (#51).
- Docs: `access-control.adoc`, `adopt.adoc`, `generation.adoc`, `questions.adoc`.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `rp-access`: deleting a tenant requires `administer`.
- `rp-tenancy`: one label for record and root; the record's version is readable on the root read.
- `rp-service-api`: `id_source`, grant and root validators, permitted actions on reads.
- `rp-generation`: technical classes exempt from ownership; `rp_service.ts` for TypeScript targets.
- `rp-testkit`: the guard and snapshot helpers are public names of `rdf_persistence.testkit`.
- `rp-package-boundaries`: the package ships a PEP 561 marker.

## Impact

- Consumers: roles that delete a tenant must hold `administer` (MWB2's owner does). MWB2 removes
  its mypy override, its public-imports allowance and its OpenAPI-generated TS types; its blocked
  v1-05 scenarios (member 403 on project delete, last owner protected, member edits title) unblock.
- `install_service` gains three optional keyword parameters; existing calls are unchanged.
- No new runtime dependency; no change to the stored data's shape.
