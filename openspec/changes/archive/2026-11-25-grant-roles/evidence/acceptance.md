# Acceptance: grant-roles

**Verdict:** accepted by the developer, 2026-11-25.

**What was shown** (lead, in-process against the toy service on a `FakeStore`, after both stages
merged at `579f283a`):

1. ADA made a tenant and a book; through `PUT …/grants`, RITA held `reader` and OMAR held both
   `reader` and `librarian` on the tenant.
2. Reading the book: RITA got `Held-Roles: reader`, OMAR `Held-Roles: librarian,reader`, each beside
   `Allowed-Actions`.
3. A `grant_roles` migration `rename: {reader: librarian}` through `migrate_shared` on the system
   database: a merge. OMAR's two grants became one `librarian` grant; RITA's was renamed.
4. The start-up report on the migrated grants: no warning.
5. OMAR read the book again: `Held-Roles: librarian`, no duplicate.
6. A second migration renamed `librarian` to `member`, which the roles file lacks: the report warned
   "grants name undefined roles" naming the tenant and `tenant:member` (RISK-3), and "no grant
   administers the tenant" (RISK-2).
7. A migration file renaming to `a,b` was refused at load (E12, D-14).

**Delivery decisions validated:** D-8 to D-15 (`design.md`, Delivery decisions), all accepted by
the developer, 2026-11-25 (R-0007).

**Found in the demo:** step 6 listed `tenant:member` once per stale grant. The developer chose to
de-duplicate it in the close (design.md D-15).
