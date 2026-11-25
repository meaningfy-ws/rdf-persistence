# Seeds: consumer-friction (secondary; never groomed)

Captured 2026-11-25 by the planner. The EPIC (`proposal.md`) is the shaped truth.

## The owner's brief

Plan one SMALL change for #371 and #372, both filed by MWB2 `v2-05` (stage 1, PR
meaningfy-ws/mapping-workbench-v2#122). Recommend one of #372's three options. Keep the scope to
the two issues: `review-floors` is re-planned in parallel and also touches the testkit.

## Issue #371: the TypeScript output copies an imported module that the Python imports

A schema may import a module that another target generates (`architecture/generation.adoc`,
"Imports between targets"). When the imported module declares `python_package`, the generated
Python imports its classes and does not generate them again. The TypeScript output does not: the
importing target writes its own copy. In MWB2, `models/values/fragment_checks.yaml` (a value module
with `python_package`) is imported by the `api` target; after `make generate`,
`frontend/src/domain/generated/values/fragment_checks.ts` (the owner's) and
`frontend/src/services/generated/fragment_checks.ts` (the `api` target's) are identical. Expected:
the importer imports from the owner's folder and writes no copy, or the docs say TypeScript always
copies. Two copies drift when one target is regenerated, and a client may import one type from two
paths.

## Issue #372: `assert_models_generated` refuses hand-written `*shapes*.ttl` fixtures

The file guard refuses every `*shapes*.ttl` under `roots` outside a `generated/` folder
(`FORBIDDEN_FILE_PATTERNS`). A consumer's hand-written SHACL fixture `tests/.../fragment_shapes.ttl`
fails it; the consumer renamed it. Workaround: `exempt=`, whose docstring says "instance data,
request bodies" and which neither the docstring nor the user manual names for test fixtures.
Options: (1) document `exempt=` for fixtures; (2) skip test folders by default; (3) a new
`allow_files=` pattern list.

## What the code says (read 2026-11-25, `develop` at 069d06d1)

- `rdf_persistence_generation/extensions/typescript.py`: `ToolkitTypescriptGenerator.modules()`
  renders every module of `schemaview.schema_map` that has classes or enums: the whole import
  closure, toolkit modules included. `render(schema_path)` adds the served types (`_with_served`)
  and the index (`with_index`). It knows nothing of the other targets.
- The Python side filters with `generated_schemas(view, folder)`
  (`rdf_persistence/schema/services/schema_structure.py`): modules naming another
  `python_package` than the root's are left to their target.
- `rdf_persistence_generation/steps.py`: `TYPESCRIPT_STEP = render_step("typescript",
  typescript.render, _typescript_folder)`; `render_step` (`pipeline.py`) calls `render(run.schema_path)`
  only. `_toolkit_packages(run)` already reads the project's targets with
  `read_targets(run.base / PYPROJECT)`.
- The TypeScript template (`templates/typescript/module.ts.jinja`) writes each import as
  `from "./{{ import.module }}"`; `TsImport` (`model/rp_generation.yaml`) has `module` and `names`.
- Stale outputs are removed through the manifest (`pipeline.py` `_remove_stale`), so a copy no
  longer written is deleted on the consumer's next run.
- The archived `domain-values-and-fixes` design, D-3, says "`typescript.py` writes only a target's
  own schemas". That is false (see above); D-3 is why the toy's value target has no `typescript`
  folder and why #371 never showed in this repository.
- The toy (`tests/fixtures/library/pyproject.toml`): the value target
  `values/loan_checks.yaml` (`tests.fixtures.library.domain.generated.values`) and the technical
  target `services/loan_checks_response.yaml`, which imports `../values/loan_checks`; neither sets
  `typescript`. Only the technical module imports `loan_checks`.
- `make typecheck-ts` runs `tsc --noEmit --strict` over `TOY_TS =
  tests/fixtures/library/web/src/domain/generated/*.ts` (CI job "types").
- `rdf_persistence/testkit/guards.py`: `exempt=` already skips folders; tests
  `test_exempt_folder_passes` and `test_exempt_does_not_cover_siblings`
  (`tests/unit/testkit/test_guards.py`) cover it with a `bad.shacl.ttl`. The user manual example
  (`user-manual/generated-classes.adoc`, *test_no_hand_written_models*) scans `tests/` and passes no
  `exempt=`: the path MWB2 followed. `architecture/generation.adoc` *Guards against hand-written
  models* already says this repository exempts `tests/fixtures/`.
- `review-floors` (branch `docs/plan-review-floors`) touches neither `guards.py` nor
  `typescript.py`; the shared file is `openspec/changes/README.md`.
