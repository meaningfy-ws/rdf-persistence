# Questions of 2026-11-15 (secondary; never groomed)

Asked at the start of epic session I, after checking the brief's claims against `develop` (ae04865).
The developer chose the recommended option each time.

1. **Application database.** The brief said every wired store must hold the application database.
   On `develop` the system and application databases live only on the one store.
   Answer: **default only.** One application database, on `default`; every store's tenant databases
   are migrated at start-up on that store.
2. **Start-up functions** (`migrate_shared`, `sweep`, `migrate_tenants`, called by consumers with
   their own start-up). Answer: **keep the signatures.** `store` means the default store; `Tenancy`
   holds the named stores; the DEC-6 check runs inside `sweep`.
3. **A tenant's store for a consumer's own SPARQL.** Answer: **`kit.store_of(tenant)`**, like
   `kit.bucket_of`; `kit.store` stays the default store.
4. **Risk: another deployment with the same prefix on a wired server.** Answer: **accept and
   document** (a prefix belongs to one deployment on every store it wires).
