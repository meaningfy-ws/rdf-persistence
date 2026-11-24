<!-- Parents: issues #307, #310 (inputs/seed.md); openspec/specs/rp-schema-migrations, rp-access.
     Q&A: inputs/qa.md (2026-11-24) and consumer-gap-fixes/inputs/qa.md round 1 (the #307 stance).
     Depends on: consumer-gap-fixes stage 2 (#306: one validation path for grants).
     Serves (D-12): MWB2 v2-06-roles-and-workflow RISK-2 / T-2 (#307: a model round that renames or
     drops a role); v2-06-discussion P-3 / T-1 (#310: the audience warning from the toolkit's rule). -->

# EPIC: Roles over time: migrate the grants that name a role, and tell a caller its roles

## Appetite

**SMALL**, in two stages, one PR each: #307, then #310. Two existing capabilities are touched in a
few places: migrations, and the access rules. There is no new concept beyond one optional section
of a migration file and one response header.

## Why

- **#307.** Roles are data converted from the UML model, so a model round can rename or drop a
  role that stored grants still name. Nothing lets a migration change grants. Such a tenant's
  grants then no longer validate, and every later `PUT …/grants` is refused. The consumer holds
  back every model round that renames or drops a role.
- **#310.** A caller cannot ask which roles it holds on an aggregate. A web app that warns before
  posting a comment with an audience the author is not in has to restate the toolkit's rule from
  the tenant grants. That copy misses aggregate grants and token roles, and it drifts.

## Solution outline

- **A grant step in a migration.** A migration file may carry `grant_roles` with `rename`
  (old → new) and `drop` (names). The toolkit turns it into operations over its own grant
  vocabulary, in the migration's one guarded, stamped request on the system database, where the
  grants live. A rename never leaves two equal grants behind. Tenant databases, the application
  database and a restore's dataset get no grant operations, since they hold no grants.
- **A start-up report.** Once the shared databases are migrated, one read of the access records
  lists every tenant whose grants name a role the role definitions do not define at that grant's
  level, and every tenant where no grant gives `administer`. Each is logged as a warning. The service
  starts, and `set_grants` can drop such a grant (see `consumer-gap-fixes`).
- **Roles held.** `Collaboration.roles_held(iri)` returns the caller's role names on an aggregate,
  by the same rule the audience check and transitions use (`AccessRules.roles`). The generic read
  of an aggregate sends them in a `Held-Roles` header beside `Allowed-Actions`.

## Key decisions

- **DEC-1:** `grant_roles` is an optional part of `Migration`, with `rename` (a map) and `drop` (a
  list), generated from the migrations services model. Rejected: a documented SPARQL recipe,
  because the consumer would then depend on toolkit internals; and a Python operation, which is
  outside the stamped chain and is not idempotent by stamp.
- **DEC-2:** the grant operations go into the request only for the system database. The request
  builder learns which database it serves, and so does the runner, which already tells the
  system database apart (`_shared_databases`). The operations sit after the steps and before the
  token rotation, so the access records get new versions.
- **DEC-3:** a rename deletes a grant whose renamed form already exists (the same assignee, target
  and new role, by the `grant_key`). Otherwise it rewrites `rp:role` in place, and the part keeps
  its IRI. A drop deletes the grant part and its link. Prohibitions carry no role and are untouched.
- **DEC-4:** the migration file is checked at load time. A dropped name may be neither a
  rename source nor a rename target. No rename target may be a renamed source (no chains). Names are non-empty. A file with
  only `grant_roles` and no steps is valid. The role definitions are not consulted at load, because
  they may be deployed in either order (RISK-3).
- **DEC-5:** the start-up report runs after `migrate_shared` and before the tenants are migrated.
  It logs `WARNING` with the step `check-grants`, the tenant id and the role names. It never stops
  start-up (owner).
- **DEC-6:** `Held-Roles` is a comma-separated list of role names in sorted order, sent on every
  generic read that sends `Allowed-Actions`. It is empty when the caller holds none. It is
  declared in the OpenAPI where `Allowed-Actions` is.
- **DEC-7:** two stages, two PRs into `develop`: #307, then #310. This EPIC lands with stage 1's PR.
  Stage 1 starts after `consumer-gap-fixes` stage 2 has merged, because both touch the grants path.

## Rabbit-holes

- The grant parts' IRIs. Owned parts are skolem or minted IRIs, not derived from content, so a
  rename in place is safe. Prove it with a round trip after the migration.
- `_request_problem` counts the operations it expects. The grant operations must be counted too,
  or every file with `grant_roles` is refused.
- `migrate_dataset` (in memory) runs the chains for a restore. It must leave grant operations out,
  and it does by DEC-2, since a dump holds no grants.
- The report reads every access record once, as `Tenancy.tenants` does. Do not open a session per
  tenant.

## No-gos

- No role definitions in the database, and no role rename outside a migration.
- No grant operations on prohibitions, on direct-action grants, or on assignees or targets.
- No per-level rename: a rename applies to every grant naming the role, whatever its level.
- No stop at start-up for stale grants.
- No `Held-Roles` on listings, and no route of its own.
- No change to how roles are computed (`AccessRules.roles`).

---

## What Changes

- Migrations: `Migration.grant_roles` (rename, drop), with load checks and operations on the
  system database.
- Start-up: a warning report of stale or empty grants.
- Collaboration: `roles_held(iri)`.
- API: the `Held-Roles` header on aggregate reads, and its OpenAPI entry.
- Docs: `howto/migrate.adoc` ("A model round renames or drops a role": the order of the roles file
  and the migration, RISK-3), `user-manual/access.adoc` (roles held, the header), and the answer
  to #307 on the issue.

## Capabilities

### Modified Capabilities

- `rp-schema-migrations`: a migration renames or drops a role in the stored grants.
- `rp-access`: a caller learns the roles it holds on an aggregate; start-up reports stale grants.

## Impact

`rdf_persistence/model/technical/migrations/rp_migrations_services.yaml` (regenerated),
`migrations/services/migrations.py`, `tenancy/services/migration_runner.py`,
`api/entrypoints/service.py`, `collaboration/services/collaboration.py`,
`api/entrypoints/router.py`, `negotiation.py`, `openapi.py`, and two docs pages. Nothing breaks:
the migration section is optional, and the header is new. Once the consumer refreshes its lock, it
ships a migration with `grant_roles` beside its renamed roles file, and its web app reads
`Held-Roles`.
