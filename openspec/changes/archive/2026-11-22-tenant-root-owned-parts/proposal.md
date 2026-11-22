<!-- Parents: issue #276; openspec/specs/rp-tenancy (tenant create), rp-iri-policy (part
     template). Serves: MWB2 v2-02 phase B (mapping-workbench-v2 PR #101) (D-12).
     Retrospective: delivered as a bug fix (PR #288, 2026-11-22) and recorded here after the
     merge, so that the spine holds the decisions and the spec gains the requirement. -->

# EPIC: A new tenant's root may own parts

## Appetite

**TINY.** One bug fix in the tenant-create path, with its tests and a toy fixture. Shaped and
recorded after delivery.

## Why

`POST /<tenants>` answered `422 charter.id: Field required` for a tenant root that owns a part.
`Tenancy.create` validated the root straight from the body, and only the generic create path
(`Documents._settled`) mints part IRIs. A consumer whose tenant root has two required owned parts
could create no tenant at all, and sending a part `id` from the client would bypass the IRI
policy.

## Solution outline

`Tenancy.create` mints the IRI of each owned part of the new root, nested parts included, from the
part template, with the tenant IRI as the root, before it validates the root. It does this the
same way an ordinary create does. A part that names its own `id` is refused.

## Key decisions

- **DEC-1:** a part `id` in a tenant-create body is an invalid body (422). The IRI policy assigns
  it, as it assigns the root's.
- **DEC-2:** the part's `{type}` comes from the owning slot's range.
- **DEC-3:** the fix lives in `Tenancy.create`, not in the router, so a direct
  `kit.tenancy.create` call gets it too.
- **DEC-4:** the toolkit's own suite covers the shape: the toy tenant root gains an optional owned
  part.

## Rabbit-holes

- A part typed as a subclass of the slot's range: the tenant-create body has no type input today
  (DEC-2). Left until a consumer needs it.
- The root's PUT: checked, it already mints parts through the documents path.

## No-gos

- No change to the generic create or replace paths.
- No client-chosen part IRIs on tenant create.

---

## What Changes

- `rdf_persistence/tenancy/services/tenancy.py`: `Tenancy.create` mints part IRIs
  (`_with_part_iris`, `_part_with_iri`) and refuses a part `id`.
- Toy library: `Library` owns an optional `Charter` (`tests/fixtures/library/library_tenant.yaml`).
  Generated files, goldens, the shape snapshot and the scenario map are refreshed.
- `user-manual/generated-classes.adoc`: the tenant-create `root` may, and must, leave a part's `id`
  out.

## Capabilities

### Modified Capabilities

- `rp-tenancy`: a new tenant's root may own parts, whose IRIs the service mints.

## Impact

Tenant create through the API and through `kit.tenancy.create`. The signature is unchanged.
Behaviour changes only for a root body that carries owned parts: it used to fail and now succeeds,
unless a part names an `id`.

## Delivery reconciliation

Delivered in one stage, PR #288, merge commit `4addd42e`, 2026-11-22. Issue #276 is closed.

| Shaped | As delivered | PR |
|---|---|---|
| DEC-1 a part `id` in the body is a 422 | As shaped | #288 |
| DEC-2 `{type}` from the slot's range | As shaped; marked with a `ponytail:` comment | #288 |
| DEC-3 the fix lives in `Tenancy.create` | As shaped | #288 |
| DEC-4 toy tenant root owns an optional part | `Library.charter` → `Charter` (`Described`) | #288 |
| Rabbit-hole: the root's PUT | Already minted; now tested | #288 |
| Rabbit-hole: subclass-typed parts | Not built (DEC-2) | — |

What Changes, Capabilities and Impact hold as written. Beyond the shape: `make refresh-map` finds
no tests on a machine whose `pytest.ini` adds `-q` (issue #290). The map was refreshed with
`--collect`.
