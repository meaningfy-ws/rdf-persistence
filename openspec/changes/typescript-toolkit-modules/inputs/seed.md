# Seeds: typescript-toolkit-modules (secondary; never groomed)

Captured 2026-11-27 by the planner. The EPIC (`proposal.md`) is the shaped truth.

## The owner's brief

Close the `typescript-client` EPIC as overtaken (archived 2026-11-27) and shape the live remainder
as its own changes. This one fixes #402. The owner accepted the planner's recommendations on
2026-11-27 ("accept recommendations; start work shaping, and the work planning").

## Issue #402: every TypeScript target re-emits the toolkit's own TypeScript

Split from #189 (item v), by the owner's answer to OPEN-5 in
`openspec/changes/review-floors/inputs/qa.md`.

> Every target that writes TypeScript re-emits the toolkit's own TypeScript modules into its own
> folder, so a project with a second target carries a second copy of the toolkit's types
> (`rdf_persistence_generation/extensions/typescript.py:154-178, 230-251`).
>
> #371 (consumer-friction, #391) stops the copy for a module that another target **of the same
> project** owns. The toolkit's own types are outside the project, so that change still copies
> them, and this issue stays open after it.
>
> Options (from the triage): a key in the target configuration that names where the toolkit's
> TypeScript modules live, which targets import by a path; or emit only the toolkit modules that a
> target's classes use. Either way, it changes the files `rp-generate` writes, so it needs its own
> EPIC on the generator's TypeScript, with a migration note.

`consumer-friction` (archived 2026-11-25) made "de-duplicating the toolkit's own TypeScript types"
a no-go of its own; its DEC-2 kept the copy because "someone must write the types". This change is
the one that no-go deferred to.

## What the code does today (checked 2026-11-27, `develop` at 801613ba)

- `steps._write_typescript(run)` calls `typescript.render(schema, folder=..., owners=...)`;
  `_typescript_owners(run)` maps the packages of the run's other targets that set `typescript` to
  their folders (#371, PD-1 of consumer-friction, revised by its D-5: from `run.targets`).
- `typescript.render` drops a module whose `python_package` is an owner's and points the kept
  modules' imports at the owner's folder (`_imported_from_owners`, `_specifier`, `_importing`), then
  `_with_served` adds every served schema's modules, merged into `rp_service.ts`, and the toolkit
  modules they import (`rp_core`, `rp_access`, `rp_tenancy`, ...). The served modules are built once
  per process (`_served_modules`, consumer-friction D-9).
- The toolkit's metamodel modules (`rdf_persistence/model/rp_*.yaml`, closure of `rp.yaml`) have
  `python_package` values under `rdf_persistence.*`, never a project target's package, so they are
  never in `owners` and every TypeScript target writes them.
- `[tool.rp-generate]` is an array of rows read by `config.read_targets` into `GenerationTarget`
  (generated from `rdf_persistence_generation/model/rp_generation.yaml`); no key spans the rows.
- The toy (`tests/fixtures/library/pyproject.toml`) has three TypeScript targets since
  consumer-friction; `web/src/domain/generated/values/` and `web/src/services/generated/` each hold
  copies of `rp_access.ts`, `rp_core.ts`, `rp_service.ts`, `rp_tenancy.ts`.
- A file a previous run wrote and this one does not is removed by `pipeline._remove_stale` (kept with
  a problem when hand-edited); `tests/generator/integration/test_stale_typescript_copy.py` proves it
  for #371.

## Consumer evidence (read-only)

MWB2 (`mapping-workbench-v2/pyproject.toml`) has four TypeScript targets: `frontend/src/domain/generated`,
`frontend/src/services/generated`, `frontend/src/domain/generated/source_intake`,
`frontend/src/domain/generated/values`. Each of the last three carries its own `rp_access.ts`,
`rp_core.ts`, `rp_service.ts`, `rp_tenancy.ts`. MWB2's triage of 2026-11-27 lists #402 as "duplicate
TypeScript files only": an interim, not a blocker.
