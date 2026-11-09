<!-- Parents: issues #42, #43, #44, #45 (filed by mapping-workbench-v2, 2026-11-08), serving MWB2
     changes v1-01-project-setup, v1-03-model and v1-05-projects-and-members (D-12).
     Seeds and the developer's answers: inputs/seed.md. -->

# EPIC: Fix what mapping-workbench-v2 met while adopting the toolkit

> Shaped 2026-11-09 from four issues; the developer answered its questions the same day
> (inputs/seed.md). PLAN: design.md + tasks.md (derived at the start of the epic session).

**Golden-thread parents:** `rp-access` (who may do what to a tenant), `rp-tenancy` (the tenant's
label), `rp-testkit` (the public test surface) and the adoption guide (`howto/adopt.adoc`).

## Appetite

**SMALL**, one stage. Four independent concerns, each in a few places; existing structure is
reused as is. One behaviour change to an existing route (DEC-1).

## Why

MWB2 is the first consumer to adopt the toolkit by the book, and it hit four places where the
toolkit contradicts itself or cannot express a common need:

1. **#42** Consumers' mypy cannot see the toolkit's types: the package ships no `py.typed`
   (PEP 561), so every typed consumer carries an override.
2. **#43** A role that may delete a tenant's aggregates may also delete the whole tenant: both
   routes check `delete`, and a Prohibition cannot separate them. MWB2's "member gets 403 when
   deleting a project" (v1-05) is blocked.
3. **#44** Renaming a tenant leaves its root object's `label` stale: the access record says "B",
   `GET /{segment}/{t}` still says "A".
4. **#45** The adoption guide's step 6 imports testkit modules that `assert_public_imports` refuses,
   so a consumer cannot follow the guide and the checker at once.

## Solution outline

- The wheel carries `rdf_persistence/py.typed`; a consumer's mypy checks calls against the
  toolkit's annotations with no configuration.
- Deleting a tenant is an administrative act: `DELETE /{segment}/{t}` requires `administer`, the
  action that already guards its grants. Aggregate deletes still require `delete`.
- A tenant has one label: `rename` writes it to the root object and the access record;
  replacing the root with a different label is refused.
- The guard helpers of step 6 and the shape snapshot helpers are names of
  `rdf_persistence.testkit`; step 6 imports only those (and documents the snapshot check), and
  `assert_public_imports` accepts it unchanged.

## Key decisions

- **DEC-1**: `DELETE` on a tenant requires `administer` on the tenant. Source: Q-1. Reason: deleting
  the tenant is an act on who may use it at all, like changing its grants; the smallest change.
  **BREAKING** for roles that hold `delete` without `administer`. Rejected: a
  `tenant_delete_action` setting (keeps the old meaning but adds configuration nobody else asked for).
- **DEC-2**: `rename` writes the new label to the root object first, then to the access record; a
  `PUT` on the root whose `label` differs from the record's is refused as an invalid body. Source:
  Q-2. Reason: the record and the root live in two datasets, so there is no single write; the record
  is the authority and is written last, and a failed rename is repaired by retrying it. Rejected:
  deriving the label when served (the stored root graph would lack its required label);
  `PUT` on the root renaming the tenant (one route changing two things).
- **DEC-3**: The guard API becomes top-level names of `rdf_persistence.testkit`, loaded lazily
  where the module is heavy (as `TokenSigner` is). `assert_public_imports` keeps its rule: only
  the two package roots (and `testkit.containers`) are public. Source: Q-3. Rejected: an allow-list
  of testkit modules (more public module paths to keep stable).
- **DEC-4**: `py.typed` is checked in the built wheel, not just in the source tree. Source: #42's
  acceptance.

## Rabbit-holes

- **Exact export names (#45).** A bare `run` at the testkit root is too vague; the PLAN fixes the
  names (design.md PD-4: `conformance_problems`). The issue's list was illustrative.
- **The freshness plugin (#45)** is loaded by the string `"rdf_persistence.testkit.freshness"` in
  `pytest_plugins`, not by an import; `assert_public_imports` reads only import statements, so it
  stays as is (checked 2026-11-09).
- **A rename that fails halfway (#44).** No compensation, no saga: the record is written last, so a
  failure leaves the old label authoritative and a retry converges. Not more.
- **Existing tenants whose root label already differs (#44).** No migration; the next rename
  repairs them.

## No-gos

- A configurable delete action, or new actions in the vocabulary (`delete-tenant`, …).
- Changing what `delete` means for aggregates, or how Prohibitions are scoped.
- Deriving or caching labels at read time; a cross-dataset transaction.
- Making more testkit modules public by path; exporting helpers the guide does not document.
- Type stubs (`.pyi`) or typing changes beyond the marker.
- Closing #24/#25: done separately (they were delivered on 2026-11-08).

---

## What Changes

- `rdf_persistence/py.typed` (new, empty) and a wheel check (#42).
- `rdf_persistence/entrypoints/router.py`: tenant `DELETE` gated by `administer`, and the docs
  that describe the gate (#43); the toy library's roles already fit. **BREAKING**: a `delete`
  Prohibition on a tenant no longer stops deleting the tenant; one of `administer` does.
- `rdf_persistence/services/tenancy.py`: `rename` updates the root's label; replacing the root with
  a different label is refused (#44).
- `rdf_persistence/testkit/__init__.py`: the guard and snapshot helpers exported, lazily where
  heavy; `docs/modules/ROOT/pages/howto/adopt.adoc` step 6 imports them (#45).

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `rp-access`: deleting a tenant requires `administer`.
- `rp-tenancy`: a rename changes the label of both the access record and the root object; a root
  replacement cannot change the label.
- `rp-testkit`: the guard and snapshot helpers are public names of `rdf_persistence.testkit`.
- `rp-package-boundaries`: the package ships a PEP 561 marker.

## Impact

- Consumers: roles that need to delete a tenant must hold `administer` (MWB2's owner role already
  does). MWB2 removes its mypy override and its public-imports allowance once this lands.
- No new dependency; no change to the stored data's shape.
