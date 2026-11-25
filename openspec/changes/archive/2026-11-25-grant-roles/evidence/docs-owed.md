# Docs owed: grant-roles

No docs owed (lead, 2026-11-25). The pages the EPIC changes were written in its stages:

- `howto/migrate.adoc`, "A model round renames or drops a role" (stage 1, PR #345): the worked
  example, the order of the roles file and the migration (RISK-3), the start-up report, a rename at
  every level, rename rather than drop a role that administers (RISK-2).
- `howto/observability.adoc`: the `rp.grants.undefined_roles` log attribute (stage 1).
- `user-manual/access.adoc`, "Ask which roles the caller holds" (stage 2, PR #367): `roles_held`,
  the `Held-Roles` header, its empty value, that it shows the caller its own role names (RISK-4),
  and that a role name holds no comma (D-13).
