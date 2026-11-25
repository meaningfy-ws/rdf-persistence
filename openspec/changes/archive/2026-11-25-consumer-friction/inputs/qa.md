# Q&A: consumer-friction (secondary; never groomed)

One round, 2026-11-25. The owner answered "yes to all": every recommendation below is accepted.

| # | Question | Recommendation (accepted) | Becomes |
|---|---|---|---|
| 1 | The #371 rule | When an imported module's `python_package` names another target of the same `pyproject.toml` and that target sets `typescript`, the importer imports the types by a relative path between the two folders and writes no copy | DEC-1 |
| 2 | When the owner writes no TypeScript (no `typescript` folder, or a module from outside the project, such as the toolkit's `rp_core.ts`, `rp_service.ts`) | Keep the copy, as today, and say so in the docs; de-duplicating the toolkit's own types is a no-go | DEC-2, no-go |
| 3 | The importer's `index.ts` | Does not export the imported module: one import path per type | DEC-3 |
| 4 | #372 option | Option 1: document `exempt=` for hand-written SHACL fixtures (docstring, user manual example, `generation.adoc`); no code, no new API. Option 2 hides a stray artefact in `tests/`; option 3 adds API for what one argument covers | DEC-4 |
| 5 | Test scenarios | (a) the toy's value and technical targets get a `typescript` folder (reverses the archived D-3, recorded); (b) a unit test: the technical target writes no `loan_checks.ts`, imports `LoanCheck` from the relative path, its `index.ts` does not export it; (c) `make typecheck-ts` (CI "types") runs `tsc --strict` over both folders; (d) an owner without `typescript` still gets the copy; (e) a guard test: `fragment_shapes.ttl` under an exempt folder passes, the same outside fails | DEC-5, design TC rows |
| 6 | Risk: the consumer's frontend | High likelihood for MWB2, low impact (`tsc` names every line): accept, flag **BREAKING** for generated TypeScript in the commit and release notes with a one-line migration; no flag to keep the copy | RISK-1 |
| 7 | Risk: path edge cases | `os.path.relpath` of the resolved folders, one unit row for a folder nested under the other, accept the rest (`tsc` catches a wrong path in CI) | RISK-2 |
| 8 | Shape | SMALL, one stage, one PR; id `consumer-friction`; worktree `.worktrees/plan-consumer-friction` on `docs/plan-consumer-friction`; spec delta on `rp-generation` only (#372 is docs only) | appetite, Capabilities |
