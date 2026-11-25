# Q&A record (secondary, never groomed): shaping session 2026-11-24

Seeds: issues #307 and #310 (`seed.md`). The backlog slice and the #307 stance come from the
owner's round 1 in `consumer-gap-fixes/inputs/qa.md`: "a migration may", meaning the toolkit
gives migration steps a supported way to rename a role in, or drop it from, a tenant's grants.

Code read on `develop` at `f9f6fa74`:

- `migrations/services/migrations.py`: `migration_request`, `_operations`, `_STEP`, `_ROTATION`,
  `_request_problem`
- `tenancy/services/migration_runner.py`: `migrate_shared`, `migrate_tenants`,
  `migrate_database`, `migrate_dataset`
- `api/entrypoints/service.py` `_run_at_startup`
- `model/rp_access.yaml`: `Grant`, `grant_key`, `role` as `rp:role`, a string
- `model/rp_tenancy.yaml` `grants`: owned parts, in the access record's graph
- `model/technical/migrations/rp_migrations_services.yaml` `Migration`
- `access/services/access.py`: `AccessRules.roles`, `defines`, `validate_grants`
- `collaboration/services/discussion.py` `thread` (the audience check uses `rules.roles`)
- `api/entrypoints/router.py` l.141 and `negotiation.py` l.25: the `Allowed-Actions` header

## Round 1

| Question | Answer |
|---|---|
| #307: how does a migration rename or drop a role in grants? | **A declarative grant step**: `grant_roles: {rename: {old: new}, drop: [x]}` in the migration file. The toolkit writes the SPARQL into the same guarded request on the system database. |
| What does start-up do about stale grants? | **Warn and list**: a warning names each tenant and each undefined role; the service starts. |
| #310: how does a caller learn its roles? | **A header and a Python call**: a header on the aggregate GET beside `Allowed-Actions`, and `Collaboration.roles_held(iri)`. |
| Risks to treat | All four: a rename makes duplicates; a drop locks a tenant out; the roles file and the migration ship apart; the header exposes role names. |

Scenarios: each issue's acceptance, plus one test per risk. This was stated in the PLAN and not
asked as a separate round.
