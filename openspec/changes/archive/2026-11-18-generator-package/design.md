> Derives from: EPIC `generator-package` ([proposal.md](proposal.md)), capabilities `rp-generation`,
> `rp-package-boundaries`, `rp-testkit`, `rp-developer-checks`.
> Type: Implementation (a move with no change of behaviour, plus tests, shims and the F-4 lookup).

## Context

Read on `docs/manual-revision-notes` (48f80c6); stage 1 re-reads it on `develop` after
`technical-models` and `otel-observability` have merged.

| Claim (analysis §5.4, improvements F) | In the code | In this PLAN |
|---|---|---|
| 8 testkit files import `generation` | Holds: `freshness`, `conformance`, `markers`, `guards`, `model_shape`, `shape_snapshot`, `zitadel`, `containers/fixtures`. Six import **only records** from `generation.generated.rp_generation`: `ContainerMarker`, `Violation`, `ClassShape`, `SlotShape`, `ExecResult`, `FusekiServer`, `GarageServer`, `ZitadelServer`, `MachineUser`, `ZitadelProject`. Only `freshness` (`config.read_targets`, `manifest.stale_targets`, `fix_hint`, `problems.format_problem`, `ConfigError`) and `conformance` (`read_targets`, `python_folder`, `ConfigError`, `ConstraintCase`, `ConstraintKind`) need generator logic | DEC-4, PD-1, PD-2 |
| — (not in the analysis) | `roundtrip.py` and `strategies.py` import `testkit.conformance.Conformance`, so they follow it | PD-2 |
| The runtime layers do not import `generation` | Holds: contract `runtime-without-extras` | DEC-3 widens it to the whole package |
| `TOOLKIT_PACKAGE`/`PUBLIC_PACKAGE` at `pydantic_split.py:54-55` | Holds; used by `metamodel_module(name, toolkit=)` from `generate_module_import`, which already refuses an import that is neither beside the root schema nor in `METAMODEL_DIR` | PD-6 |
| — (not in the analysis) | `manifest.recorded_path` writes every input under `PACKAGE_DIR` as `rdf_persistence/...`, and `_toolkit_files()` lists `GENERATION_DIR`'s modules and templates as inputs of **every** target, so the move changes every manifest (`tests/fixtures/library/generated/rp-manifest.json` lists `rdf_persistence/generation/*.py`) | PD-4, RISK-2 |
| — (not in the analysis) | `schema_structure.is_toolkit_schema(folder)` is `folder` under `PACKAGE_DIR`; it gates PD-23's exemptions in `apply_defaults`, `checks/hard.py:389`, `checks/boundary.py:144` and `pydantic_split.py:169` | PD-5 |
| `uv_build` can ship two top-level packages | Checked while shaping: `module-name = ["a", "b"]`, `module-root = ""` on `uv_build` 0.10 builds one wheel with both | DEC-1 |
| A consumer imports `rdf_persistence.generation` | Not found: the docs name it only in `develop/index.adoc:90` (this repository's own rule) and `architecture/index.adoc:314`; consumers use the plugin path `rdf_persistence.testkit.freshness` (`howto/adopt.adoc:363`) and the testkit names (`adopt.adoc:391`) | DEC-5 |
| — (found by the attack) | Library tests outside `tests/unit/generation/` use the generator as a tool: `tests/conftest.py:37` loads the freshness plugin; `tests/unit/entrypoints/test_service_written.py`, `tests/unit/services/test_replace_internal_values.py` and `tests/integration/api/test_router.py` call `generation.cli.main`; `tests/unit/services/test_collaboration_{workflow,discussion}_adversarial.py` call `checks.hard.hard_problems`; `tests/unit/services/test_activity_shape.py` and `test_mapper.py` import `testkit.conformance`, `testkit.roundtrip`, `testkit.strategies` | PD-9 (allow-list) |
| — (found by the attack) | The generator's call sites of `is_toolkit_schema`, `apply_defaults` and `generation_view` are `components.py:43`, `extensions/shacl.py:130`, `extensions/typescript.py:173`, `extensions/pydantic_split.py:169,172`, `checks/hard.py:389`, `checks/boundary.py:144`, `lock_step.py:44`, `testkit/conformance.py:95`; `pipeline.py` has none. The library's `testkit/shape_snapshot.py:26` calls `generation_view` too | PD-5 |
| — (found by the attack) | `tests/unit/generation/test_shape_snapshot.py:198` checks the generator's own schema (`GENERATION`, `GENERATION_PACKAGE`) with the library's `class_shapes`; `Makefile:93,96` (`refresh-snapshot`, `refresh-golden`), `ruff.toml:61` and `.pre-commit-config.yaml:24` name `rdf_persistence/generation` | PD-9, PD-10 |
| — (found by the attack) | `install_service` needs a store, a file store and an identity provider (`tests/e2e/library_app.py:59`); `tests/e2e/conftest.py` registers the container fixtures plugin; the library's `e2e/` row stamps `STORE, FILES, IDENTITY` | PD-9, PD-13 |
| — (found by the attack) | `tests/unit/test_testkit_lazy_import.py` sits in `tests/unit/`, not `tests/unit/testkit/` | task 2.2 |

`technical-models` (2nd, `openspec/changes/technical-models/proposal.md`) delivers before this
change: D-4 replaces `FIELD_OF_TOML_KEY` with model aliases in `generation/config.py` and adds a
case model to `conformance.py` and a shape model to `model_shape.py`; its DEC-1 puts technical
schemas in `model/technical/<group>/`, each generated into the `generated/` folder of the lowest
layer that uses it, one target per group with a `kind` key. Its PD-11 and task 4.1 create the
library's `testkit` group, `model/technical/testkit/rp_testkit.yaml`, generated into
**`rdf_persistence/testkit/generated/`**, and move into it, once, every record a testkit module
that stays in the library imports: `ClassShape`, `SlotShape`, `ContainerMarker`, `Violation`,
`MachineUser`, `ZitadelProject`, `ZitadelServer`, `ExecResult`, `FusekiServer`, `GarageServer`,
plus the new `FieldFlags`. `ConstraintCase` and `ConstraintKind` stay in `rp_generation.yaml`: their
only user is `testkit/conformance.py`, which this change moves to the generator (DEC-4). Settled in
the cross-change reconciliation of 2026-11-17; stage 1 here is the import cut and its contract.

## Goals / Non-Goals

**Goals:**

- `rdf_persistence` imports nothing from `rdf_persistence_generation`, the testkit included, apart
  from the four named shims (DEC-3).
- `rp-generate`, `[tool.rp-generate]` and `rp-generate --check` without the `generate` extra behave
  as today, from the new package.
- `make check-generated` is byte-identical before and after, except the manifests' input paths.
- The generator's tests stand in their own pyramid and CI job (DEC-8, DEC-9).
- The metamodel's import packages come from the metamodel (DEC-7).

**Non-Goals:** everything in the EPIC's No-gos.

## Decisions

Settled in the EPIC and cited, not re-argued: DEC-1 to DEC-10. The new ones:

- **PD-1 The testkit records.** The library's `testkit` group is `technical-models`' (its PD-11:
  `rdf_persistence/model/technical/testkit/rp_testkit.yaml`, package
  `rdf_persistence.testkit.generated`, target `kind = "technical"`, `openapi = false`), and it
  already holds every record a library testkit module imports. This change moves no record and
  does not rename the package. Stage 1 checks that no module of `rdf_persistence/testkit/` but
  `freshness.py` and `conformance.py` imports from `rdf_persistence.generation` (TC-01) and adds the contract that
  keeps it so (task 1.2). `ConstraintCase` and `ConstraintKind` stay in `rp_generation.yaml` and
  go with the conformance suite to the generator in stage 2, where they are the generator's own
  records. `rp_generation.yaml`'s description stops mentioning the testkit. If a record was added
  to a library testkit module after `technical-models` merged, task 1.1 moves it into the
  `testkit` group in the same way, and says so in the PR.
- **PD-2 The generator's testkit.** `rdf_persistence_generation/testkit/` holds `freshness.py`
  (the pytest plugin), `conformance.py`, `roundtrip.py`, `strategies.py`, and an `__init__.py` that
  exports `Conformance`, `conformance_problems`, `round_trip`, `aggregate` lazily, as
  `rdf_persistence.testkit` does today (pyshacl and hypothesis load on first use). The plugin path
  becomes `rdf_persistence_generation.testkit.freshness`.
- **PD-3 The shims (DEC-5).** Each of `rdf_persistence/testkit/{freshness,conformance,roundtrip,strategies}.py`
  becomes a module that calls `warnings.warn(..., DeprecationWarning, stacklevel=2)` once, naming
  the new module, and re-exports that module's public names by explicit `from ... import` (the
  freshness shim re-exports `pytest_addoption` and `pytest_sessionstart`, so the old
  `pytest_plugins` line still works). `rdf_persistence.testkit._LAZY_NAMES` keeps the four names,
  pointing at the shim modules. Each shim's docstring names the release that removes it (the minor
  after the one that ships this change). The contract of PD-8 lists exactly these four edges in
  `ignore_imports`. A follow-up issue, opened at stage 2's PR, tracks the removal.
- **PD-4 Manifest paths.** `recorded_path` records a file under the library's folder as
  `rdf_persistence/...` and a file under the generator's folder as `rdf_persistence_generation/...`;
  anything else stays relative to `base`. `_toolkit_files()` lists the library's `schema*.py`
  readers (as today) and the generator's modules and templates, excluding its `generated/`. The
  generator's folder is `GENERATOR_DIR = Path(str(resources.files("rdf_persistence_generation"))).resolve()`,
  in the generator.
- **PD-5 Toolkit schemas.** The library's `is_toolkit_schema(folder, *, roots=(PACKAGE_DIR,))`,
  `apply_defaults(view, folder, *, roots=...)` and `generation_view(path, *, roots=...)` take the
  folders that count as the toolkit's, defaulting to the library's. The generator defines
  `TOOLKIT_ROOTS = (PACKAGE_DIR, GENERATOR_DIR)` and passes it at every call site, the nine of
  Context: `components.py:43`, `extensions/shacl.py:130`, `extensions/typescript.py:173`,
  `extensions/pydantic_split.py:169,172`, `checks/hard.py:389`, `checks/boundary.py:144`,
  `lock_step.py:44`, `testkit/conformance.py:95` (line numbers as of 48f80c6; stage 2 re-reads
  them with ast-grep). A unit test runs the ast-grep patterns `is_toolkit_schema($$$A)`,
  `apply_defaults($$$A)` and `generation_view($$$A)` over `rdf_persistence_generation/` and fails
  on a match without `roots=`, so a call site added later cannot miss it. The library's
  `testkit/shape_snapshot.class_shapes(paths, *, roots=(PACKAGE_DIR,))` gains the same keyword and
  passes it to `generation_view`. The library never names the generator. Rejected: the library
  finding the generator by name with `importlib.util.find_spec` (a hidden reverse dependency).
- **PD-6 F-4 lookup.** `GenerationAnnotation` gains `python_package` (on a toolkit schema module:
  the package its classes are generated into) and `public_package` (on `model/rp.yaml`: the package
  a consumer's generated code imports metamodel classes from). Every flat `model/rp_*.yaml` carries
  `python_package: rdf_persistence.domain.generated`; each `model/technical/<group>/rp_<group>.yaml`
  carries the `package` of its target (`rdf_persistence.services.generated.<group>` for `service`,
  `settings`, `templates` and `telemetry`, `rdf_persistence.adapters.generated` for `wire`, and
  `rdf_persistence.testkit.generated` for `testkit`); `rdf_persistence_generation/model/rp_generation.yaml`
  carries `rdf_persistence_generation.generated`; `rp.yaml` carries
  `public_package: rdf_persistence`. `generate_module_import` only ever resolves a metamodel module
  (it refuses any other, `pydantic_split.py:85-89`), so the lookup is narrow:
  `metamodel_module(schema, *, toolkit)` takes the imported `SchemaDefinition` it is already given
  and returns `<its python_package>.<name>` when `toolkit`, else the `public_package` read once
  (`functools.cache`) from `load_schema(METAMODEL_DIR / "rp.yaml")`. The constants are deleted,
  along with the constant import in `test_ext_pydantic_split.py`. A new hard-check rule, run on the toolkit's own
  targets only: (a) a toolkit schema module without `python_package`, and (b) a module whose
  `python_package` differs from the `package` of the toolkit `[[tool.rp-generate]]` entry that
  generates it, are each a problem naming the module and both values. A consumer's run reads the
  annotations and never checks (b), since the toolkit's `pyproject.toml` is not in the wheel.
- **PD-7 Packaging.** `pyproject.toml`: `[tool.uv.build-backend] module-name = ["rdf_persistence",
  "rdf_persistence_generation"]`; `rp-generate = "rdf_persistence_generation.cli:main"`; the
  generator's target `schema = "rdf_persistence_generation/model/rp_generation.yaml"`,
  `package = "rdf_persistence_generation.generated"`. `rdf_persistence_generation/py.typed` exists.
  `EXTRA_HINT` is unchanged (`install rdf-persistence[generate]`).
- **PD-8 Import contracts.** `.importlinter` takes `root_packages = rdf_persistence
  rdf_persistence_generation`. New `library-never-imports-the-generator` (forbidden; source
  `rdf_persistence`; forbidden `rdf_persistence_generation`; `ignore_imports` the four shim edges).
  `runtime-without-extras` forbids `rdf_persistence_generation` instead of
  `rdf_persistence.generation`. `works-without-the-generate-extra` lists
  `rdf_persistence_generation.{cli,config,manifest,pipeline,exceptions,problems,generated,testkit}`,
  `rdf_persistence.testkit`, `rdf_persistence.services.schema` and `.schema_structure`, keeping the
  one `cli -> steps` ignore. The layers contract is unchanged; its comment no longer names
  `generation`.
- **PD-9 Test layout and stamping (DEC-8).** `tests/conftest.py::_MARKERS_BY_DIR` gains
  `generator/unit/` (unit), `generator/feature/` (feature), `generator/integration/` (integration,
  no container marker), `generator/e2e/` (e2e, `STORE`, `FILES`, `IDENTITY`, as the library's
  `e2e/` row, because `install_service` needs all three). Tests that test the library stay in the
  library's pyramid: `test_metamodel_schema.py` and `test_schema_loading.py` go to
  `tests/unit/services/`; `test_model_guard.py` and `test_shape_snapshot.py` to `tests/unit/testkit/`,
  except the `generation` parameter of `test_generated_classes_match_the_induced_slots`, which
  checks the generator's own model and moves to `tests/generator/unit/test_generation_shape.py`
  (calling `class_shapes(..., roots=TOOLKIT_ROOTS)`). The `refresh-snapshot` target follows the file.
  Every other file of `tests/unit/generation/` (with `conftest.py` and `golden.py`), and
  `tests/unit/testkit/test_freshness_plugin.py`, go to `tests/generator/unit/`.
  A library test does not import `rdf_persistence_generation`, with one named exception: a test
  that uses the generator **as a tool** on the library's own schemas. The checker
  (`tests/unit/test_library_tests_stay_apart.py`) reads every `tests/**/*.py` outside
  `tests/generator/` with `ast` (`Import`, `ImportFrom`, and string constants passed to
  `pytest_plugins` or `importlib.import_module`) and fails naming each file that imports the
  generator and is not in its `TOOL_USERS` set. `TOOL_USERS` is exactly the files of Context
  that stay: `tests/conftest.py` (the repository's own `pytest_plugins` line, rewritten to
  `rdf_persistence_generation.testkit.freshness`), `tests/unit/entrypoints/test_service_written.py`,
  `tests/unit/services/test_replace_internal_values.py`, `tests/integration/api/test_router.py`,
  `tests/unit/services/test_collaboration_workflow_adversarial.py`,
  `tests/unit/services/test_collaboration_discussion_adversarial.py`,
  `tests/unit/services/test_activity_shape.py` and `tests/unit/services/test_mapper.py`. Each keeps
  testing the library; its imports are rewritten to the new paths (the last two to
  `rdf_persistence_generation.testkit.{conformance,roundtrip,strategies}`, never the shims). A file
  leaves `TOOL_USERS` when it stops importing the generator; the checker also fails on an entry that
  no longer imports it, so the set cannot go stale. Rejected: moving these eight files into
  `tests/generator/` (they test the library's service, collaboration and mapper behaviour; the
  generator's coverage would count library tests).
- **PD-10 Lanes (DEC-9).** `make test-unit` and `make test-feature` add `--ignore=$(TEST_PATH)/generator`
  and keep `--cov=rdf_persistence` and their floors. New `make test-generator`: `pytest
  tests/generator -n auto -m "unit or feature or integration"` with
  `--cov=rdf_persistence_generation --cov-fail-under=80`. `make test` runs the three. `test-fast`
  and `test-changed` run over all of `tests/` as today. `make test-containers` runs
  `-m "integration or e2e"` over all of `tests/`, so it includes the generator's integration and
  end-to-end tests. `tests/changed.py` maps a changed `rdf_persistence_generation/...` file to
  `tests/generator/`. `PYTHON_PATHS`, `make typecheck`, `clean-code`/radon, `check-docs`
  (`CODE_DIRS`) and `sonar.sources` name both packages. The paths that name
  `rdf_persistence/generation` today follow the move: `Makefile:93` (`refresh-snapshot`, to
  `tests/generator/unit/test_generation_shape.py` and `tests/unit/testkit/test_shape_snapshot.py`),
  `Makefile:96` (`refresh-golden`, to `tests/generator/unit`), `ruff.toml:61` and the `files:`
  regex of `.pre-commit-config.yaml:24`; a `grep -rn "rdf_persistence/generation\|rdf_persistence\.generation"`
  over the repository outside `openspec/` and `CHANGELOG.md` finds nothing at the end of stage 2.
  CI job `test-generator` sets up Node 20 and runs `make test-generator`. Coverage stays above the
  floors: on the last full run (`coverage.xml`, 2026-11-16) the library without `generation/` is at
  97.4 % of lines and `generation/` alone at 96.6 %.
- **PD-11 Feature tests.** `tests/generator/feature/generation.feature` with steps in
  `tests/generator/feature/test_generation.py`. Each scenario copies the toy library's schemas
  (`tests/fixtures/library/*.yaml`, `migrations/`, `pyproject.toml`) to `tmp_path` and runs
  `rp-generate` through `cli.main` there. They need the `generate` extra, as the unit tests do.
- **PD-12 Integration tests.** `tests/generator/integration/`: the toy freshly generated once per
  session into `tmp_path_factory`, then (a) pySHACL validates the conformance fixtures'
  (`tests/fixtures/conformance/`) valid and invalid instances against the fresh `shapes.ttl`;
  (b) PyLD expands a toy JSON body with the fresh `context.jsonld` and frames it back with a fresh
  frame; (c) `npx -y -p typescript@5.9.3 tsc --noEmit --strict` (the Makefile's pin) on the fresh
  TypeScript. Missing Node is a failure that says to install Node, never a skip.
- **PD-13 End-to-end test.** `tests/generator/e2e/test_generated_library_served.py`: the toy copied
  to `tmp_path/toy_e2e/`, generated with `--package toy_e2e.generated --python-out
  toy_e2e/generated`, imported with `tmp_path` on `sys.path` (removed after), then served with
  `install_service` on the testkit's store, file store and identity fixtures (Fuseki, Garage,
  Zitadel), as `tests/e2e/library_app.py` wires it minus the scan routes.
  `tests/generator/e2e/conftest.py` registers the container fixtures plugin as
  `tests/e2e/conftest.py` does. It proves the spec's end-to-end scenario on freshly generated
  code. Marked `slow`.

## Algorithm / approach

Stage order: **1** one-way testkit (in place) → **2** the move → **3** F-4 → **4** the upper tiers.
Stage 2 is one PR because a half-moved package does not import.

Stage 2, step by step:

1. `git mv rdf_persistence/generation rdf_persistence_generation`; add `py.typed`.
2. Rewrite imports with one ast-grep rule over `rdf_persistence_generation/`, `rdf_persistence/`,
   `tests/` and `docs/tools/`: `rdf_persistence.generation` → `rdf_persistence_generation`, and the
   generator's relative paths (`PACKAGE_DIR / "generation" ...` in `config.GENERATION_MODEL` and
   `manifest.GENERATION_DIR`) to `GENERATOR_DIR / ...`.
3. Move the four testkit modules (PD-2), write the shims (PD-3).
4. PD-4, PD-5, PD-7, PD-8.
5. `make generate`. Expected diff: only the `rp-manifest.json` files (every toolkit target and
   the toy), and only in input paths. Anything else stops the stage.
6. Move the tests (PD-9), add the lanes (PD-10), then the docs.

Worked example of a consumer upgrading (messages abridged):

```text
$ uv sync                      # rdf-persistence 0.N, with [generate,testkit]
$ make test                    # pytest_plugins = ["rdf_persistence.testkit.freshness"]
DeprecationWarning: rdf_persistence.testkit.freshness moved to rdf_persistence_generation.testkit.freshness ...
generated code is not fresh:
pyproject.toml: STALE app/generated: input rdf_persistence/generation/cli.py is gone ...
run `make generate-models` to regenerate, then commit the result
$ make generate-models         # only rp-manifest.json changes
```

Idempotency: the move and the regeneration are deterministic (PD-19); running `make generate` twice
gives the same tree. The shims warn once per process (module import).

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Import the generator from the library, even lazily by a string | The shims of PD-3, listed in the contract | A string import hides from import-linter (DEC-3) |
| Let the library find the generator's folder by name | Pass `roots` from the generator (PD-5) | A reverse dependency by another route |
| Edit a generated file or a manifest by hand during the move | `make generate` | PD-19, DEC-10 |
| Move a library test into `tests/generator/` because it once sat in `tests/unit/generation/` | Place by the module it tests (PD-9) | The two pyramids must measure their own package |
| Skip a `tsc` test when Node is missing | Fail with the install hint | A skip hides a gate |
| Add the `pytest11` entry point for convenience | Keep `pytest_plugins` (DEC-6) | Every session of every project would be checked |
| Change a template while moving | A separate change | No-go: output must stay byte-identical |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| A library module imports the generator | `make check-architecture`, `library-never-imports-the-generator` | Fails, naming both modules |
| A library test imports the generator | The PD-9 `ast` test | Fails, naming the file, unless it is in `TOOL_USERS` |
| A `TOOL_USERS` entry no longer imports the generator | The PD-9 `ast` test | Fails, naming the stale entry |
| A generator call site of `is_toolkit_schema` / `apply_defaults` / `generation_view` without `roots=` | The PD-5 ast-grep test | Fails, naming file and line; without it the generator's own schema would get consumer defaults |
| A testkit module still imports a record from `rp_generation` after `technical-models` | TC-01 (task 1.1) | Fails, naming the module and the record |
| A path still names `rdf_persistence/generation` (Makefile, ruff, pre-commit, docs) | The `grep` of PD-10 at the close of stage 2 | The stage does not close |
| The wheel lacks the generator, its templates, model or `py.typed` | `tests/unit/test_packaging.py` | Fails, naming the missing path |
| `rp-generate` run without the `generate` extra | `cli._pipeline_steps` | Exit 2 with `EXTRA_HINT`, as today; `--check` compares manifests only, as today |
| A consumer's manifest names `rdf_persistence/generation/...` | The freshness plugin / `rp-generate --check` | Session stops with STALE and the consumer's regenerate command (RISK-2) |
| A consumer imports an old testkit path | Shim | Works, with one `DeprecationWarning` naming the new path |
| A consumer imports `rdf_persistence.generation` | Python | `ModuleNotFoundError` (no shim, DEC-5); the release notes name the new package |
| A metamodel module lacks `python_package` | Hard check on the toolkit's run | Problem naming the module; nothing written |
| `python_package` disagrees with the toolkit target's `package` | Hard check on the toolkit's run | Problem naming the module and both packages |
| The generator's own schema is checked by consumer rules after the move | `make generate` hard-check problems, or a diff in `rp_generation.py` | Prevented by PD-5; caught by step 5 of the stage |
| Node missing in the generator integration lane | `FileNotFoundError` from `npx` | Test fails with "install Node 20" |
| A container (Fuseki, Garage, Zitadel) down in the generator e2e test | Container fixture | Fails as the library's e2e does |

## Risks / Trade-offs

- **RISK-1 Merge conflicts with the parallel changes.** `technical-models` and `otel-observability`
  edit files under `generation/` and `testkit/`. Likelihood high if they overlap, impact medium
  (rework). Mitigation: stage 2 starts only after both merged to `develop`, is done in one session
  with the ast-grep rule, and other open branches rebase with `git mv`-aware merges.
- **RISK-2 Every consumer's freshness check fails once after the upgrade.** Likelihood certain,
  impact low (one command; the hint names it). Accepted; the release notes and the commit body say
  "run your regenerate command once". Rejected: mapping old paths to new ones in the comparison
  (code kept forever for a one-time step).
- **RISK-3 A consumer imports a moved name we did not find.** Likelihood low (analysis §5.3 lists
  five imported modules), impact: an `ImportError` at its test start. Mitigation: shims for every
  moved testkit path; the release notes list the moves.
- **RISK-4 The shims outlive their release.** Likelihood medium, impact: DEC-3 stays half-true.
  Mitigation: the follow-up issue (PD-3), and the shim docstrings name the release.
- **RISK-5 `thematic-structure` moves the library modules the generator imports** (`schema_structure`
  18 times, `schema` 11). Likelihood certain, impact low: the generator's imports change in the
  same PR as each move, inside one repository. Accepted; it is the reason for DEC-1.
- **RISK-6 The generator's CI job is slower than the others** (Node, `tsc`, one toy generation per
  session). Likelihood medium, impact low. Mitigation: one session-scoped generation (PD-12); the
  job runs in parallel with the others.
- **RISK-7 A consumer without the `generate` extra imports `rdf_persistence_generation.testkit`.**
  It works: the testkit part imports no `linkml` (PD-8 contract). Accepted as a feature.
- **RISK-8 `technical-models` lands differently from what PD-1 reads** (another package for the
  `testkit` group, or a different set of moved records). Likelihood low (the two PLANs were
  reconciled on 2026-11-17 and its TC-50 asserts the cut), impact low: stage 1 is a delta over
  what merged.
  Mitigation: task 1.1 starts by re-reading `rp_generation.yaml` and every testkit import on
  `develop`; TC-01 and TC-02 are stated over "what a testkit module imports", not over a fixed list.
- **RISK-9 `TOOL_USERS` grows into a back door.** Likelihood low, impact medium (DEC-8's split
  blurs). Mitigation: the set is a literal in the checker, so adding a file is a reviewed diff, and
  a stale entry fails (PD-9).

## Open Questions

None that block. For the developer's round: the shim lifetime ("one minor release") and the
package name are leader's choices (DEC-2, DEC-5).

## Delivery decisions

- **D-1 One session for both EPICs** (developer, 2026-11-17). `generator-package` and
  `thematic-structure` are delivered in one autonomous session, every stage, overriding "one EPIC
  per session, fresh session per stage". Mitigation: after each merge the lead re-reads this
  change's `handover.md` and `tasks.md` before the next stage; after any compaction it re-reads
  `handover.md` before acting.
- **D-2 The acceptance demo is waived** (developer, 2026-11-17, before the autonomous run), although
  LARGE makes it mandatory. Recorded in `evidence/acceptance.md`.
- **D-3 Review set** (lead). Per P-0005 each stage gets one pass of L2 and L3, replacing the
  per-stage sets in `tasks.md` (stage 1 L1+L3, stage 2 the five lenses, stage 3 L1+L3+L4); the
  full review (L1, L2, L3 apart, L4+L5 one pass) runs once, on stage 4, over the whole EPIC's diff.
- **D-4 Tester** (lead). The PLAN has no `## Invariants` section, so at LARGE the adversarial
  tester runs on every stage that changes code; its probes are the PLAN's "adversarial tester,
  reverted" rows (TC-06, TC-14a, TC-23, TC-24) plus the error matrix.
- **D-5 Preconditions** (lead, 2026-11-17, on `develop` 14b3a86). `technical-models`,
  `otel-observability` and `manual-revision-notes` are archived. RISK-8 did not occur: only
  `testkit/freshness.py` and `testkit/conformance.py` import `rdf_persistence.generation`; every
  other record is in `rdf_persistence.testkit.generated`, so task 1.1 moves nothing.
- **D-6 Stage 1 is a small stage** (lead). About 100 added lines (one test file, one contract, a
  description sentence), no production code: the one L2+L3 pass is the four-eyes pass and the full
  gates with CI are the check, with no separate checker. The tester's probe (TC-06) was run by the
  builder of task 1.2 and reverted.
- Stage 1 review, under the floor (Warning and Suggestions, not fixed):
  - W: `test_testkit_imports.py` skips relative imports; the import-linter contract still catches
    them, and no testkit module uses one. Stage 2 rewrites the test for the new package.
  - S: `architecture/generation.adoc` does not name the interim contract; stage 2 rewrites the
    passage (task 2.5).
  - S: the contract's comment says "configuration and records" while `freshness` also uses the
    manifest logic; the name is fixed by task 1.2 and stage 2 replaces the contract.
- **D-7 PR #161 does not block the move** (lead, 2026-11-18, under the developer's "take the
  decisions for me"). The ordering rule allows no open PR but release-please (#134) and the lead's
  own before stage 2. #161 (the developer's) changes only `.gitignore`, which no move touches, so
  stage 2 starts. A parallel session merged #163 (`mrn-followups`) into `develop` meanwhile; stage 2
  branches after it (c11961b) and rebases before its PR (P-0002).
- **D-8 Stage 2 runs its tasks in parallel where their files are disjoint** (developer, 2026-11-18,
  "run things in parallel whenever they can"). 2.1 first (nothing imports half-moved); then 2.2,
  2.3 and 2.5 in parallel worktrees; 2.4 after 2.2 (both edit `tests/conftest.py`). Builders do
  not tick `tasks.md`; the lead does (T2).
- **D-9 Stage 2's impact is CRITICAL, accepted** (lead, under the developer's grant to decide).
  GitNexus rates `is_toolkit_schema` (4 direct callers, 108 symbols to depth 3) and
  `recorded_path` (4 direct, 13 to depth 3) CRITICAL. Expected for the move: the direct callers
  are the call sites PD-5 lists, the new `roots=` keyword defaults to today's behaviour, and the
  only output change allowed is the manifests' input paths (TC-09), which `make check-generated`
  and the full gates check.
- **D-10 `assert_isomorphic` stays in the library** (lead, found by the builder of task 2.2). It is
  defined in `roundtrip.py`, which PD-2 moves, but it is a generic graph comparison that about ten
  library tests import through `rdf_persistence.testkit`: after the move each of them loaded a shim
  and the generator, warned at collection and reached the generator from a library test (PD-9).
  It moves to a library testkit module of its own, `rdf_persistence/testkit/graphs.py`;
  `_LAZY_NAMES` points it there; the generator's `roundtrip.py` imports it from there (generator →
  library is the allowed direction) and the `roundtrip` shim keeps re-exporting it. Rejected:
  rewriting the library tests to the generator's path (a library test would import the generator).
- **D-11 `tasks.md` §2.2 names two test paths wrongly** (builder of 2.2): `test_stage1_adversarial.py`
  does not exist (the four lazy names are tested in `tests/unit/testkit/test_lazy_guard_names_adversarial.py`)
  and `test_testkit_lazy_import.py` is in `tests/unit/testkit/`. The builder used the real files.
- **D-12 The shims are removed in 0.6.0** (builder of 2.2, PD-3): `VERSION` is 0.4.0, the
  release-please PR proposes 0.5.0, which ships this change. If it ships later, the four shims,
  their warnings and `test_the_removal_release_is_named_in_every_shim` take the new number.
- **D-13 `TOOL_USERS` after the attack's list** (lead, builder of 2.4 asked). Three library test
  files outside PD-9's eight import the generator, all added after the PLAN was read:
  `tests/feature/test_technical_models.py` runs `rp-generate` on scratch technical-group projects,
  a tool use on the library's own model layout: it joins `TOOL_USERS` (nine entries).
  `tests/unit/testkit/test_testkit_imports.py` imports `rp_generation` only to check a record is not
  defined there: it reads `rp_generation.yaml` instead, and leaves the set.
  `tests/unit/testkit/test_testkit_target_adversarial.py::test_a_check_problem_replaced_keeps_what_it_does_not_name`
  tests the generator's `CheckProblem`: it moves to `tests/generator/unit/`, as PD-9 split the
  shape test.
- **D-14 Path-keyed test data follows the move** (lead). `tests/audit/scenario-map.csv` and
  `.test_durations` key tests by path; the lead regenerates them with `make refresh-map` and
  `make test-durations` before the stage's gates, never by hand.
- **D-15 The generator's coverage reaches SonarCloud** (lead; within PD-10). The new
  `test-generator` CI job writes `coverage-generator.xml`; it is uploaded and listed in
  `sonar.python.coverage.reportPaths`, so the generator's lines stop counting as uncovered.
  As built (after D-19 W2): the generator uploads `generator-coverage`; a `sonar` job that needs
  `unit` and `test-generator` (`if: always()` and `SONAR_ENABLED`) downloads both reports and
  scans; `unit` needs only `unit-shard`.
  `coverage-generator.xml` is git-ignored like the other reports.
- **D-16 Stage 2 tester findings** (lead; tester: 100 tests, 16 failed first, 7 findings).
  Accepted: (1, P1) `test_testkit_moved.py` did not collect after the lead's merge — fixed with
  D-13; (4, P4) `.test_durations` names moved files — fixed by D-14's refresh, its two tests kept.
  Under the floor (not fixed; their failed-first tests deleted in the sort):
  - (2, P3) the `roots=` guard (TC-14a) misses calls through a module attribute and `roots=` in a
    comment or another keyword, and crashes when a function is no longer called;
  - (3, P3) the PD-9 checker does not read annotated or augmented `pytest_plugins`,
    `__import__` or `pytest.importorskip`;
  - (5, P4) `rp-generate --list-python-folders` needs the `generate` extra although it writes
    nothing;
  - (6) `hasattr(testkit, "aggregate")` without hypothesis raises; deliberate, pinned;
  - (7, nit) the freshness report repeats a stale generator module once per target.
  Filed together as a follow-up issue (linked in Open of `handover.md`). TC-14c's "nothing" allows
  the migration note in `howto/adopt.adoc`, which names the old path on purpose.
- **D-17 The scenario map follows moved tests** (lead, found running D-14). `make refresh-map`
  drops the rows of a test whose file moved (493 rows here) and lists it again as unmapped, so
  a move loses its traceability. `tests/audit/refresh_map.py` gains moves: a row whose test file
  was renamed (`git diff --name-status -M <base>`, or a `--moved OLD=NEW` pair) is re-keyed to
  the new path instead of dropped; `make refresh-map` passes `BASE` (default `develop`).
  `thematic-structure` moves every test folder too, so it needs this as well. The new tests of
  the change are mapped by the lead before the archive (`make refresh-map` exits 0).
- **D-18 The `assert_isomorphic` identity test moves to the generator's pyramid** (lead). D-10's
  test that the name is one object through the generator's `roundtrip` imports the generator from
  `tests/unit/testkit/`, which the PD-9 checker refuses; it moves to
  `tests/generator/unit/test_testkit_moved.py`. The no-warning test stays in the library.
- **D-19 Stage 2 review (L2+L3), accepted findings** (lead). C1 (`.test_durations` keeps moved
  ids) is D-14's fix, `--clean-durations`. Re-labelled Critical, with the reason:
  - W1 → Critical: `event-bus-libraries-in-one-module` and `sparql-parser-only-through-the-wrappers`
    have `source_modules = rdf_persistence`, which no longer covers the generator. The move
    narrowed two enforced contracts, which is a weakened gate. Both add `rdf_persistence_generation`.
  - W2 → Critical: the `unit` job (library floor, SonarCloud) `needs` `test-generator`, so a
    generator-only failure skips it, against the `rp-developer-checks` scenarios "a generator
    change" and "parallel jobs" of this change. The scan moves to its own job that needs both
    (`unit` needs only `unit-shard` again); D-15 holds through that job.
  - Lead's check: `tests/generator/unit/test_roots_call_sites.py` runs the `ast-grep` binary,
    which is neither a dependency nor installed in CI, so `test-generator` would fail in CI. The
    guard is rewritten with Python's `ast` (PD-5 allows an equivalent walk): a call of the three
    functions, by name or through a module attribute, with no `roots` keyword is a problem, and
    no call at all is no problem. This also closes #164 item 1.
  Owed to the docs stage (`evidence/docs-owed.md`): W3 `howto/adopt.adoc` says the `generate`
  extra installs the generator (one wheel ships both; the plugin needs no extra); W4 `AGENTS.md:45`
  and `CONTRIBUTING.md:46` describe the old layout; W5 `develop/index.adoc` commands table (three
  lanes, `test-generator`, `refresh-map` moves); W6 `architecture/index.adoc:209` and
  `questions.adoc:216` place the freshness plugin in the library. Under the floor: S1 (TC-14c also
  allows the tests that prove the old path absent), S2 ("the testkit alone" does not assert no
  generator module loads), S3 (three docstrings name `generation`), S4 (the model guard's
  `layers=("",)` and the generator half of `test_model_guard.py`), S5 (`test_generation_shape.py`
  imports helpers from a library test).
- **D-20 Stage 2 checker: verdict fail, items fixed now** (lead, under the developer's grant;
  checker: 6 findings, no Critical). Fixed in one fixer pass, then one full-gates run:
  - W1 (TC-09 deviates): `_toolkit_files()` takes every module under the generator but
    `generated/`, so the moved `testkit/` (freshness plugin, conformance, round trip, strategies)
    became an input of every manifest, and editing it would mark every consumer stale although it
    never shapes the output. `testkit/` is excluded like `generated/`; the manifests are
    regenerated (PD-4).
  - W2: no test fails if `library-never-imports-the-generator` is deleted or its ignores relaxed,
    or if the event-bus and SPARQL contracts stop covering the generator (D-19 W1); the contracts
    join the kept-contracts tests of `tests/unit/test_technical_split.py`.
  - W3, evidence recorded here: TC-31, the test count over `tests/` before and after the moves of
    task 2.4 was 7765 both (builder of 2.4, `make test-fast` totals); TC-23, a planted
    `import rdf_persistence_generation.config` in `services/schema.py` broke
    `library-never-imports-the-generator` and `runtime-without-extras` naming both modules
    (builders of 2.3 and the tester); TC-24, a planted `import linkml` in the generator's
    `manifest.py` broke `works-without-the-generate-extra` (same); TC-09, the lead read the
    regenerated diff of task 2.1: only `rp-manifest.json` files changed (nine targets and the toy),
    input paths and the hashes of edited generator modules; outputs are R100 renames.
  Under the floor: S1 (scenario-map rows, done before the archive per D-17), S3 (a guard that the
  generator's integration tier loads no container plugin: stage 4, task 4.2). S2 (hand-over and
  ticks) is the PR's last commit.
- **D-21 Stage 4's test tiers are built while stage 3 runs** (lead, under the developer's "run
  things in parallel"). Tasks 4.1 to 4.3 add only new files under `tests/generator/{feature,
  integration,e2e}/` and do not depend on F-4, so their builders start from stage 2's merge
  (b60c963) in parallel with task 3.1. They are committed onto stage 4's branch, cut from
  `develop` after stage 3 merges, and their gates run there; stage 3 and stage 4 remain one PR
  each, in order.
- **D-22 Stage 3's impact is CRITICAL, accepted** (lead). `metamodel_module` has 2 direct callers
  (`generate_module_import` and its test) and reaches 114 symbols to depth 3 through generation;
  the output must not change (TC-40), which `make check-generated` checks. GitNexus's MCP index
  reads the main checkout (still before the move), so its counts are indicative.
- **D-23 Task 3.1 as built** (builder of 3.1, accepted by the lead). (1) TC-39 cannot hold
  literally: PD-6's own key `public_package` generates the enum member
  `GenerationAnnotation.PUBLIC_PACKAGE`; it is an `ast` check that no constant `TOOLKIT_PACKAGE`
  or `PUBLIC_PACKAGE` is assigned, imported or used. (2) `rp.yaml` also carries
  `python_package: rdf_persistence.domain.generated`: rule (a) needs it on every module of the
  toolkit target, and `rp.yaml` is one. (3) The two rules live in `checks/python_package.py`, run
  by the hard step with the target's `package`; TC-35 to TC-37 assert the problem, and "nothing
  written" holds by the pipeline's rule that a failing hard step blocks every write.
- **D-24 Stage 3 is a small stage; its review** (lead). About 450 added lines, one task: one L2+L3
  pass, the tester, the full gates and CI, no separate checker (as D-6). Review: 7 findings, no
  Critical. Owed to the docs stage: W1 (`architecture/generation.adoc`: the two `HardRule`
  members, the toolkit's run checks its own modules' `python_package`, the two annotations in
  the table), W2 (a new technical group also needs `python_package` on its schema), S3
  (`develop/index.adoc` "Add a check rule": a rule with its own module joins
  `steps._hard_problems`). Under the floor: W3 (TC-37 is tested in two halves; the consumer run
  against a disagreeing metamodel holds by reading, `is_toolkit_schema` returns early), S1 (no
  end-to-end "writes nothing" test for the two rules), S2 (TC-38 plants no fault in a technical
  schema), S4 (`pydantic_split.py`'s docstring cites another change's DEC-6).
- **D-25 Stage 3 tester** (lead; 35 tests, 13 failed first, 3 findings, none accepted). Under the
  floor, added to #164: (P2) `public_package` is not validated, so a malformed value in `rp.yaml`
  would make a consumer write a broken import (only the toolkit edits `rp.yaml`); (P3)
  `metamodel_module` does not validate `python_package` itself (rule (b) catches it on the
  toolkit's run); (P3) `public_package()` is cached over a module constant, stale only in tests
  that swap the metamodel. The sort keeps the end-to-end tests of the two error-matrix rows
  (which also closes the review's S1) and the consumer half of TC-37 (W3).
- **D-26 Tasks 4.1 to 4.3 as built** (builders, accepted by the lead). (1) TC-44: through
  `rp-generate` a class without a `description` is refused by the lint step (the toolkit's
  `lint.yaml` makes LinkML's `recommended` rule an error), which runs before the hard check; the
  scenario asserts the lint problem naming the class and `description`, exit 1, nothing written;
  the `[description]` tag stays pinned by the unit test of the hard check. (2) TC-47: the toy's
  `closed` invalid cases are refused by `Documents.expand` (`InvalidBody`) before SHACL, so their
  `ClosedConstraintComponent` is not asserted; any other kind refused that way fails the test.
  (3) PD-13: `--python-out` is not passed; the toy's own `python = "generated"` already writes into
  `toy_e2e/generated`, and the flag would nest it a level deeper. (4) The e2e test reuses
  `tests.e2e.world.Callers` and `library_app.library_settings`, coupling the generator's e2e to
  the library's e2e helpers; `build_library_app` is bound to the committed toy, so the wiring is
  repeated in a small `served` helper.
- **D-27 The full review of the EPIC** (lead; D-3: L1, L2, L3 apart, L4+L5 one pass, over
  `14b3a86..e9d0cc5`, after stages 1–3 merged). No finding was labelled Critical; re-labelled,
  with the reason, and fixed in one fixer pass:
  - L3 W1 → Critical: the pre-commit `rp-generate-check` hook fires only on
    `rdf_persistence_generation/model/`, while every generator module is a manifest input; the move
    narrowed a gate (DEC-10). It matches the whole generator but `testkit/` and `generated/`
    (PD-4, D-20), pinned by a test.
  - L2 W1 + W2 → Critical: `tests/generator/e2e/conftest.py` registers the container plugin for any
    session that collects `tests/generator`, so the unit lanes (`test-fast`, `test-changed`,
    `test-generator`) import testcontainers and run its autouse fixture, and the integration
    tier's "no container plugin" guard cannot fail. The unit lanes ignore `tests/generator/e2e`
    like `tests/e2e`; the guard asserts the plugin is not registered in the session.
  Accepted below Critical because each is the same class as an earlier fix: L3 S2 (pin the
  sources of `works-without-the-generate-extra` and `rdf_persistence_generation` among the
  forbidden modules of `runtime-without-extras`, as D-20 W2); L2 W3 (`architecture/generation.adoc`
  ~683 and `develop/index.adoc` ~134: the manifest inputs also exclude `testkit/`, D-20 W1);
  L2 S5 (tick 4.1–4.3).
  Under the floor, follow-ups in #164: L1 S1 (`refresh_map --base` value starting with `-` is read
  by git as an option); L3 S1 (a contract keeping the generator's core off its testkit, pytest and
  hypothesis); L2 W4 (`assert_public_imports` does not know the generator's public surface);
  L2 S1–S4 (TC-46/47 silently drop rows outside the toy, TC-44/45 "nothing written" checks only two
  folders, TC-41 checks two frames, TC-47's `closed` refusal reason); L4+L5 W1 (three copies of
  "copy and generate the toy"), W2 (three `ast` import walkers), W3 (constraint kinds as bare
  strings in the integration test), S1–S10 (duplicated constants and helpers).
- **D-28 Stage 4 tester** (lead; 11 planted regressions, 7 caught by the tiers, 4 gaps; 4 tests,
  all failed first against their plant and pass on the clean tree). Accepted, closed by the kept
  tests, no production change: (1, P2) TC-42 generates twice in one process and cannot see
  hash-seed nondeterminism — three generations under different `PYTHONHASHSEED`; (2, P2) TC-41
  checks two frames — every activity class gets one; (3, P2) the closed shapes' exemption for the
  session's bookkeeping predicates had no upper-tier test; (4, P3) TC-54 covered only the passing
  path — cleanup when the body raises or the import fails. Under the floor, already in #164
  item 11: (5) TC-44's step does not pin the `[description]` tag (D-26), (6) "nothing written"
  checks two folders. The tester's note that no make target runs one generator tier is a
  suggestion, not filed.
- **D-29 Stage 4 checker: verdict fail, items fixed now** (lead, under the developer's grant;
  9 findings). C1 (Critical): D-27's guard asserts the container plugin is absent from the
  session, but `make test-containers` loads it on purpose and selects the integration tier too,
  so the container gate fails; the guard asserts absence only when the session ignores
  `tests/generator/e2e` (the lanes D-27 pins), and holds nothing otherwise. W1: the
  `develop/index.adoc` commands table (`make test` runs three lanes, no "two halves",
  `refresh-map` re-keys moved tests against `BASE`) is done now (D-19 W5, D-17). W2: `proposal.md`'s
  As built names D-28. W3: the 14 new tests are mapped (D-17), in this PR. W4: the hook's docstring
  and `generation.adoc` (~713) say it fires on the generator's inputs, not "every manifest input"
  (the library's `schema*.py` readers are inputs it does not match, as before the move). Under the
  floor: S2 (a cleanup test asserts `sys.path` only), S3 (a direct `tests/generator/e2e` path given
  to `test-changed` loads its conftest, as `tests/e2e` does), S4 (docs-owed has no status column).
- **D-30 The docs stage is folded into stage 4's PR** (lead, under the developer's "work in
  parallel" and "do not stop"). The owed pages were written while stage 4 was built, from the
  same base, and land in PR 4 instead of a separate docs PR; the full review's L2 pass and the
  stage 4 checker verified every row of `evidence/docs-owed.md` against the code, and a cold
  reader read the changed how-to (`howto/adopt.adoc`). The archive follows as its own PR.
