# Q&A: typescript-toolkit-modules (secondary; never groomed)

One round, 2026-11-27, asked in the session that closed `typescript-client` and split its
remainder. The owner answered "accept recommendations; start work shaping, and the work planning":
every recommendation below is accepted. Questions the round did not ask are the planner's choices,
marked so; the owner may overrule them.

| # | Question | Recommendation (accepted) | Becomes |
|---|---|---|---|
| 1 | Split of the related issues | #417 its own TINY change (it blocks a consumer merge); #415, #397, #387, #386 one EPIC (`consumer-write-rules`); #402 its own SMALL EPIC (this one), BREAKING | appetite, scope |
| 2 | #402: where the toolkit's TypeScript lives | One target is named as the owner of the toolkit's TypeScript modules; every other TypeScript target imports them from it by a relative path, reusing #371's mechanism. A project with one TypeScript target is unchanged. With several and no owner named, `rp-generate` stops with a clear message and a fix hint. BREAKING, with a migration note | DEC-1, DEC-2, DEC-3, DEC-6 |
| 3 | What the EPIC must prove | With two TypeScript targets the toolkit modules are written once, the other target imports them, `tsc --strict` passes; copies left by an earlier run are removed; a single-target project is unchanged; several targets without the setting fail with a clear message | spec scenarios, design TC rows |
| 4 | Risks | The owner accepts no risk (2026-11-27, for the client work: "none"): each risk gets a mitigation | RISK-1 to RISK-4 |

Planner's choices (not asked; recorded so the owner can overrule):

| # | Choice | Why | Becomes |
|---|---|---|---|
| P1 | The setting is a per-entry boolean, TOML key `toolkit-typescript` | `[tool.rp-generate]` is an array of rows with no project-level place; a flag on the owning row names it where its folder is | DEC-2, PD-1 |
| P2 | The owner writes a fixed shared set (every metamodel module of `rp.yaml`'s closure and the served types), not only its own closure's toolkit modules | An importer may need a toolkit module the owner's schema does not import; a fixed set needs no cross-target schema loading | DEC-4, PD-3 |
| P3 | A toolkit module outside the shared set (a technical module a consumer imports itself) is still copied | It is not in the owner's fixed set; copying keeps `tsc` green | DEC-5 |
| P5 | The migration note covers a consumer that skipped #371 too | Evidence (2026-11-27): a consumer still on an older release imports service types such as `TenantSummary` and `InUseProblem` from importer folders; upgrading past this change and #371 together needs both migrations (toolkit types to the owner's folder, a co-owned module to its owning entry's folder) | design.md PD-9 |
| P4 | No `.feature` files | The precedent of a generator-only SMALL change (`consumer-friction`) proves its scenarios with generator unit and integration tests and the CI "types" job | design.md Test plan |
