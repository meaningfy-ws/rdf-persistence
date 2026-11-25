# Design: consumer-friction

> Derives from: EPIC `consumer-friction` (proposal.md, DEC-1 to DEC-6). Facts: `inputs/seed.md`;
> the owner's answers: `inputs/qa.md`.

## Context

`TYPESCRIPT_STEP` (`rdf_persistence_generation/steps.py`) is `render_step("typescript",
typescript.render, _typescript_folder)`, and `render_step` calls `render(run.schema_path)`: the
TypeScript render sees one schema and no other target. `ToolkitTypescriptGenerator.modules()`
renders every module of the closure that has classes or enums. The Python step leaves a module to
its owner through `generated_schemas`; the TypeScript step has no equivalent. `_toolkit_packages`
in the same file already reads the project's targets with `read_targets(run.base / PYPROJECT)`.

## Decisions

- **PD-1 Who owns a module's TypeScript.** `steps._typescript_owners(run) -> dict[str, Path]`:
  when `run.base / PYPROJECT` is a file, `{t.package: Path(t.typescript) for t in
  read_targets(run.base / PYPROJECT) if t.typescript and t.package != run.target.package}`;
  otherwise `{}` (a flags-only run copies, as today). Folders are relative to `run.base`, as
  `_typescript_folder` treats them.
- **PD-2 The step.** `TYPESCRIPT_STEP` becomes a `Step("typescript", _write_typescript,
  writes=True)` in `steps.py`, whose `_write_typescript(run)` returns when `_typescript_folder(run)`
  is `None`, otherwise does what `render_step`'s `write` does (inside `schema_faults()`, then
  `stage`) with `typescript.render(run.schema_path, folder=<own folder>, owners=_typescript_owners(run))`.
  `render_step` is unchanged (the other steps use it). The step keeps its name and position in
  `STEPS`.
- **PD-3 Which modules are imported.** In `typescript.render(schema_path, *, folder: Path | None =
  None, owners: Mapping[str, Path] = {})` (defaults keep today's behaviour for every other caller):
  a module of `generator.modules()` is *imported* when its schema's `python_package_of(schema)`
  (from `schema_structure`) is a key of `owners` and differs from the root's
  `python_package_of(generator.schemaview.schema)`. Order inside `render`: drop the imported
  modules, then rewrite the kept modules' imports (PD-4), then call `_with_served`. The rewrite
  must come first because `_with_served` renders the text (`_file`); it is safe there because
  `_pointing_at_merged` and `_merged` only remap names in `served_names`, which never name a
  project module. The served-type merge is untouched.
- **PD-4 The specifier.** For an imported module `m` owned by folder `O`, from the own folder `F`:
  `spec = posixpath.relpath((O / m).as_posix(), F.as_posix())`; if `spec` does not start with
  `"."`, prefix `"./"`. Each kept module's `TsImport` whose `module` is an imported module's name
  gets `module=spec`; the template renders `from "{{ import.module }}"` when `import.module`
  starts with `"."`, else `from "./{{ import.module }}"` as today. No new slot in
  `rp_generation.yaml`: `TsImport.module` holds the module name or, for another target's module,
  its relative path. That is said in `TsImport`'s `slot_usage.module.description`, not on the
  shared slot `module` ("The name of a schema module."), which another class also uses;
  `make generate`. Imports stay sorted by `module`, so a `"../.."` specifier sorts before plain
  names; the golden files fix that order.
- **PD-5 The index.** `with_index` already exports exactly the files written; a dropped module has
  no file, so DEC-3 needs no code. A test proves it.
- **PD-6 The toy (DEC-5).** `tests/fixtures/library/pyproject.toml`: the value target gets
  `typescript = "web/src/domain/generated/values"`, the technical target
  `typescript = "web/src/services/generated"`. The D-3 comment above the value target is replaced
  by one naming this change. `Makefile` `TOY_TS` adds
  `$(wildcard tests/fixtures/library/web/src/domain/generated/values/*.ts)` and
  `$(wildcard tests/fixtures/library/web/src/services/generated/*.ts)`. The trees are written by
  `make generate` and committed. The domain target's tree and `golden/served_typescript/` do not
  change (only the technical module imports `loan_checks`).
- **PD-7 #372 (DEC-4), docs only.** `assert_models_generated`'s docstring: `exempt`: "folders the
  file guard skips: instance data, request bodies, hand-written test fixtures such as SHACL shapes
  or contexts". `user-manual/generated-classes.adoc`: the example passes
  `exempt=[ROOT / "tests" / "fixtures"]`, and the paragraph after it says a hand-written fixture
  named like a generated artefact (`fragment_shapes.ttl`) goes under an exempt folder.
  `architecture/generation.adoc` *Guards against hand-written models*: one sentence, the same.
  A docstring edit changes no behaviour; the existing tests `test_exempt_folder_passes` and
  `test_exempt_does_not_cover_siblings` already prove the mechanism, and task 1.3 adds the
  `*shapes*.ttl` case the issue names.
- **PD-8 Docs for #371.** `architecture/generation.adoc` *Imports between targets*: a paragraph
  that the TypeScript step follows the same rule when the owner sets `typescript` (relative import,
  no copy, not in `index.ts`), and copies otherwise, the toolkit's own types included.
  `user-manual/generate.adoc`, the `typescript` row of the output table: "one file per module the
  target owns, `index.ts`, `rp_service.ts`; a module another target writes as TypeScript is
  imported from that target's folder". `CHANGELOG.md` `[Unreleased]`, *BREAKING* (DEC-6): "a
  module another target writes as TypeScript is no longer copied into the importing target's
  folder; import its types from the owner's folder".

## Algorithm / approach

Worked example (the toy after PD-6). The technical target's run: own folder
`F = web/src/services/generated`, root package `tests.fixtures.library.services.generated`.
`owners` = `{tests.fixtures.library.domain.generated: web/src/domain/generated,
tests.fixtures.library.domain.generated.values: web/src/domain/generated/values}`.
`loan_checks` names `tests.fixtures.library.domain.generated.values` → imported, dropped.
`loan_checks_response`'s import of `LoanCheck` (and any other `loan_checks` type it names) gets
`module = posixpath.relpath("web/src/domain/generated/values/loan_checks", "web/src/services/generated")`
= `"../../domain/generated/values/loan_checks"`, rendered as
`import type { LoanCheck } from "../../domain/generated/values/loan_checks";`. The folder holds
`loan_checks_response.ts`, the served and toolkit modules, `index.ts`; no `loan_checks.ts`.
The value target's own run has `owners` without its own package: it writes `loan_checks.ts`.

Nested case (spec scenario 2): `F = web/src/domain/generated`, `O = web/src/domain/generated/values`,
`relpath` → `"values/loan_checks"` → `"./values/loan_checks"`.

## Error matrix

| Input / state | Behaviour |
|---|---|
| Owner target sets no `typescript` | not in `owners` → copied (DEC-2, spec scenario 3) |
| Owner outside the project (toolkit metamodel, `rdf_persistence.*`) | not in `owners` → copied (DEC-2) |
| Flags-only run, no `pyproject.toml` | `owners = {}` → copied, as today |
| The run's own package in `[tool.rp-generate]` twice | own package excluded by PD-1; a module naming it is the target's own |
| Root names no `python_package` | root package `None`; a module naming an owner's package is still imported (`None` ≠ it). Deliberately unlike `generated_schemas`, which keeps every module when the root names none: here only modules of another target that writes TypeScript are dropped, and PD-1 already excludes the run's own package |
| The owner's `typescript` is added or removed later | `pyproject.toml` is not a manifest input, so `rp-generate --check` (freshness) still reports the importer fresh; `make check-generated` (regenerate, then `git diff`) catches the stale tree. Accepted; making `pyproject.toml` an input is out of this appetite |
| An imported module that defines nothing (no classes, no enums) | not in `modules()`, nothing to drop or import |
| Owner's folder is written later in the same run, or not yet regenerated | the import names a file the owner writes; `tsc` in CI (`make typecheck-ts`) fails if it is missing (RISK-2) |
| A copy written by an earlier run | not in the outputs any more → removed by `_remove_stale`, or kept with a problem if hand-edited (spec scenario 4) |
| An imported module is a served schema | cannot happen: served schemas are toolkit modules, never a project target's package |

## Anti-patterns

- Filtering by folder (as `own_schemas` does) instead of by `python_package`: the value module of
  MWB2 sits in another folder, but a same-folder module with another package must also be imported
  (the package test `generated_schemas` applies when the root names a package).
- Passing the owners through module state or an environment variable: they go in as arguments.
- Writing a TS barrel or path alias config: relative paths only (no-go).

## Test plan

| TC | Scenario | Proof | Tier / lane |
|---|---|---|---|
| TC-1 | spec 1 | the technical target's run: no `loan_checks.ts`; `loan_checks_response.ts` holds `from "../../domain/generated/values/loan_checks"`; `index.ts` has no `"./loan_checks"` | generator unit, `make test-generator` |
| TC-2 | spec 1 | two `run_toy` runs, one per new target, each in its own staging folder; each tree equals the committed files (`assert_matches_toy`, globs `web/src/domain/generated/values/*.ts` and `web/src/services/generated/*.ts`), since `assert_matches_toy` compares the whole staging set | generator unit |
| TC-3 | spec 1 | `make typecheck-ts` compiles the three toy folders together. It fails with `TS2307 Cannot find module '../../domain/generated/values/loan_checks'` when the specifier or the owner's file is wrong, and `TS2305` when a name is not exported there. Needs Node: it runs in the CI "types" job, and locally only where `npx` is present | CI "types" (`make check-types`) |
| TC-4 | spec 2 | `typescript.render` on a `toy_copy` whose owner folder is nested under the importer's: `from "./values/loan_checks"` | generator unit |
| TC-5 | spec 3 | `typescript.render(..., owners={})` for the technical schema writes `loan_checks.ts` and exports it | generator unit |
| TC-6 | spec 4 | a full run (`rp-generate` over a `toy_copy` whose technical target first ran without the value target's `typescript`, then with it) leaves no `loan_checks.ts` in `web/src/services/generated` | generator integration, `tests/generator/integration/`, `make test-generator` |
| TC-7 | #372 | `fragment_shapes.ttl` under an exempt folder passes; the same name outside it fails naming it | unit, `tests/unit/testkit/test_guards.py` |
| TC-8 | gate | `make check-generated` (freshness) clean for the toy and the toolkit | `make check-all` |

The domain target's existing tests (`test_ext_typescript.py`, `golden/served_typescript`) pass
unchanged: they are the regression guard that a target with no imported module writes the same.

## Risks

- **RISK-1 (DEC-6) the consumer's frontend breaks on regeneration.** Likelihood high for MWB2,
  possible for any consumer with two TypeScript targets; impact low (`tsc` names each import).
  Accepted; mitigated by the CHANGELOG *BREAKING* line with the migration, and the PR naming
  MWB2's `v2-05` (D-12).
- **RISK-2 a wrong relative path.** Folders given as absolute paths or outside the project could
  yield a wrong specifier. Mitigated by `posixpath.relpath` on the configured (project-relative)
  folders, TC-4 for nesting, TC-3 in CI; the rest accepted (the consumer's own `tsc` catches it).
- **RISK-3 a toolkit target is affected.** Checked while planning: no target of the toolkit's
  `pyproject.toml` sets `typescript`, so `_typescript_owners` is empty on the toolkit's run and its
  generated `.py`, `.ttl`, `.jsonld` and `.ts` cannot change. The `rp-manifest.json` files do
  change (every generator file and template is a recorded input, `manifest.py`
  `_toolkit_files`), and so do `rp_generation`'s own artefacts (the `slot_usage` description,
  PD-4). Task 1.1 confirms no other diff.
- **RISK-4 a merge conflict with `review-floors`** in `openspec/changes/README.md` only; resolved
  by whichever PR merges second.

## Lanes for moved or rewritten tests

None moved or rewritten. TC-1, TC-2, TC-4, TC-5 run in the generator's unit lane and TC-6 in its
integration lane, both in `make test-generator`; TC-7 in the library's unit lane; TC-3 in the CI
"types" job.

## Delivery decisions

- **D-1 (2026-11-25, developer).** Authority grant for this EPIC: the lead commits, pushes, opens
  the stage PR and merges it on green CI without asking at each step; nothing destructive; the
  grant ends with the EPIC.
- **D-2 (lead, Prepare).** Tasks 1.1 and 1.3 touch disjoint files and run as parallel builders, 1.3
  in its own worktree (`.worktrees/consumer-friction-372`, branch `change/consumer-friction-372`),
  its commit cherry-picked onto `change/consumer-friction`. Tester: no, SMALL. Review set: one pass
  (L2 with L3, `develop/agents.adoc#challenge`).
- **D-3 (lead, Build).** Against `develop`, `make test-changed` cannot map the generator's
  changes and falls back to the whole suite (32 min in task 1.1). Tasks 1.2 and 1.4 run their gate
  with `BASE=<the stage head before the task>`, so it maps only the task's own files. The three
  tests that failed under load in 1.1's gate (`test_transaction_attack.py` twice,
  `test_sparql.py::test_a_pattern_too_long_for_the_parser_is_refused_with_the_advice_to_split`)
  pass alone; the stage's `make check-all` decides whether they are flakes.
