<!-- Parents: openspec/specs/rp-generation (rp-generate, freshness, LinkML single source);
     openspec/specs/rp-package-boundaries (layers, public API, typed package); openspec/specs/rp-testkit;
     openspec/specs/rp-developer-checks (CI jobs, lanes); archive/2026-11-06-toolkit-v1-foundation PD-2
     (linkml behind the `generate` extra), PD-18, PD-19, PD-26. Seeds: ../manual-revision-notes/inputs/
     seed.md, answers-2026-11-17.md (Q-3), improvements.md (F-1..F-4), analysis.md §5.3, §5.4, keep.md. -->

# EPIC: The generators as a sibling package

> Shaped 2026-11-17 from the `manual-revision-notes` initiative; the developer answered Q-3 the
> same day and delegated the packaging choice. Every DEC marked "leader's choice" may be overruled.
> **Position: 4th** of the five changes of the initiative, plus `ldes-view` later. Depends on
> `technical-models` (D-4 replaces `FIELD_OF_TOML_KEY` with model aliases; the testkit records
> become technical models) and lands after
> `otel-observability`, which edits the same modules. Must land before `thematic-structure`, which
> needs F-4 to place each theme's generated classes.

**Golden-thread parent:** capability `rp-generation` and the developer's need (seed, Q-3):
"reliable generators ... which could be used also outside the repo for the apps building on top of
this toolkit", with "the tests for the generators ... separate (e2e, feature, unit, integration)".

## Appetite

**LARGE.** One boundary moves between owners: the generator leaves `rdf_persistence` for a sibling
top-level package in this repository, the testkit stops depending on it, its tests get their own
pyramid and CI job, and the metamodel's package layout becomes configuration. About 4 000 lines
move with no change of behaviour; the new code is the tests, the shims and the F-4 lookup. Four
stages, one PR each.

## Why

The generator lives inside the runtime package and the testkit, which every consumer imports,
depends on it: eight testkit files import `rdf_persistence.generation`. Its 38 unit test files are
mixed with the library's, and nothing above the unit tier checks it: acceptance is "regenerate and
diff". The hard-coded `TOOLKIT_PACKAGE` (`pydantic_split.py:55`) blocks `thematic-structure`, which
must place generated classes per theme.

## Solution outline

The repository ships **one distribution with two top-level packages**: `rdf_persistence` (the
library, unchanged for a running service) and `rdf_persistence_generation` (the generator, its
model, templates and its test helpers). LinkML stays behind the `generate` extra, so the generator
is present everywhere and usable at development time only when the extra is installed.

```text
rdf_persistence/              the library; never imports the generator
rdf_persistence_generation/   cli, pipeline, checks/, extensions/, templates/, model/, generated/,
                              testkit/ (freshness plugin, conformance, round trip, strategies)
tests/{unit,feature,integration,e2e}/            the library's pyramid
tests/generator/{unit,feature,integration,e2e}/  the generator's pyramid
```

The dependency becomes one-way, generator → library, enforced by import-linter. A consumer keeps
`rp-generate`, its `[tool.rp-generate]` table and, for one minor release, the old testkit import
paths, which warn. The metamodel declares where its generated classes live, and the generator
reads that instead of two constants. The generator gains feature tests over the toy library,
integration tests of its output against pySHACL, PyLD and `tsc`, and an end-to-end test that
serves a freshly generated toy library on Fuseki.

## Key decisions

- **DEC-1** (Q-3; leader's choice, the developer may overrule): **one distribution**,
  `rdf-persistence`, ships both top-level packages (`uv_build` `module-name` as a list; checked on
  `uv_build` 0.10 while shaping). The generator's dependencies stay behind the existing `generate`
  extra: the parameterised install the developer asked for. F-2 (a second distribution in a uv
  workspace, later a sibling repository) is superseded by the developer's Q-3 answer ("not a
  sibling repository but a sibling python module ... not sure we need it as a separate
  distribution"). Reason: one version to release and pin;
  generator and metamodel change together. Rejected: a second distribution in a uv workspace (two
  versions to release and pin, no present need; it is the upgrade path if the release cadences
  diverge); a sibling repository (metamodel changes would need two ordered PRs and releases).
- **DEC-2** (leader's choice): the package is named **`rdf_persistence_generation`**. Reason: the
  present module path with the dot made an underscore, so every import rewrite is mechanical and
  easy to grep. Rejected: `rp_generate` (reads as the command, and too short to be unique on PyPI
  installs); `rdf_persistence_generator` (a second word for one thing).
- **DEC-3**: **the library never imports the generator**, `rdf_persistence.testkit` included; an
  import-linter contract enforces it. The only exceptions are the deprecation shims of DEC-5,
  named one by one in the contract's `ignore_imports` and removed with them.
- **DEC-4** (F-1; leader's choice): the testkit is split by what each file needs. Files that need
  only **records** (`markers`, `guards`, `model_shape`, `shape_snapshot`, `zitadel`,
  `containers/fixtures`) stay in the library, and their records live in the library's technical
  group `testkit` (`model/technical/testkit/rp_testkit.yaml`, generated into
  `rdf_persistence/testkit/generated/`), which `technical-models` creates and fills (its PD-11,
  task 4.1); this change moves no record, it cuts the imports and adds the contract.
  (re-shaped 2026-11-17 by the lead in the cross-change reconciliation: the records move once, in
  `technical-models`, into the package path of its DEC-1 and DEC-2.) Files that need the generator's
  **configuration** (`freshness`, `conformance`, and `roundtrip` and `strategies`, which build on
  `conformance`) move to `rdf_persistence_generation.testkit`. Rejected: moving all eight files
  (six of them test the library or its containers, not generated output); moving `config`,
  `manifest` and `GenerationTarget` into the library (that is generator logic, and the dependency
  would point back).
- **DEC-5** (leader's choice): compatibility for consumers. Unchanged: the `rp-generate` command,
  the `[tool.rp-generate]` table and its keys, the `generate` extra, the fix hint. For **one minor
  release**, `rdf_persistence.testkit.{freshness,conformance,roundtrip,strategies}` and the testkit
  names `Conformance`, `conformance_problems`, `round_trip`, `aggregate` remain as shims that
  re-export the moved objects and raise a `DeprecationWarning` naming the new path; the release
  after removes them. No shim for `rdf_persistence.generation`: no consumer imports it (analysis
  §5.3: the consumer imports five modules, none of them this one). Rejected: no shims (breaks a
  consumer's `pytest_plugins` line on upgrade); permanent shims (DEC-3 would never hold).
- **DEC-6** (leader's choice): the freshness plugin stays **opt-in** (`pytest_plugins`), with no
  `pytest11` entry point. Reason: with one distribution it is installed everywhere, and a project
  without a `[tool.rp-generate]` table would have every session stopped. Rejected: auto-loading.
- **DEC-7** (F-4; leader's choice): where the toolkit's generated classes are imported from is
  **declared in the toolkit's schemas**, as LinkML annotations the generator reads:
  `python_package` on each toolkit schema module (the flat `model/rp_*.yaml` and each
  `model/technical/<group>/` schema), `public_package` on `model/rp.yaml`. The toolkit's own run
  fails a hard check when an annotation is missing or disagrees with the `[[tool.rp-generate]]`
  entry that generates the module. Reason: the metamodel YAML ships in the wheel and a consumer's run reads it, while
  the toolkit's `pyproject.toml` does not ship; `thematic-structure` then moves a module by editing
  one annotation. Rejected: `[tool.rp-generate]` keys (each consumer would restate the library's
  layout); keeping the constants (blocks E-1).
- **DEC-8** (F-3; leader's choice): the generator's tests live in
  **`tests/generator/{unit,feature,integration,e2e}`**, tiers stamped by folder as today; the
  library's stay in `tests/{unit,feature,integration,e2e}`. Rejected: tests inside the package
  (shipped in the wheel); a `generator/` subfolder in each tier (four places to filter and move).
- **DEC-9** (leader's choice): CI gains one job, **`test-generator`**: the generator's unit, feature
  and integration tests (pySHACL, PyLD, `tsc` on Node; no containers) with an 80 % coverage floor
  over `rdf_persistence_generation`. It runs on every PR, with no path filter: the generator
  depends on the library, so a library change can break it. The generator's end-to-end test needs
  Fuseki and runs in `make test-containers`, locally, like the library's (CI runs no containers).
- **DEC-10** (keep.md): committed generated code, `check-generated` and `check-freshness` stay. The
  library's own models are still generated by the generator, now the sibling package.

## Rabbit-holes

- **The manifests record generator paths.** `manifest.recorded_path` writes
  `rdf_persistence/generation/...` for every generator source as an input of every target. After the
  move each manifest, the consumer's too, names `rdf_persistence_generation/...`, so every consumer
  must run `rp-generate` once after upgrading. The generated code itself does not change.
- **"Toolkit schema" is decided by path** (`schema_structure.is_toolkit_schema`, PD-23). The
  generator's own schema leaves `rdf_persistence/`, so without care it would be checked by the
  consumer rules and generated with consumer defaults. The generator must count its own folder as
  the toolkit's without the library knowing the generator's name.
- **Moving files under two parallel changes.** `technical-models` and `otel-observability` edit
  generation and testkit files. Stage 2 is one mechanical move that starts after both have merged.
- **The bootstrap.** `make generate` regenerates the library's models with the generator, which
  imports the library. The move must keep `make check-generated` byte-identical apart from the
  manifests.

## No-gos

- A second distribution, a uv workspace or a sibling repository (DEC-1 names the upgrade path).
- Changing any generated artefact other than the manifests' input paths; changing the templates'
  output.
- Renaming `rp-generate`, the `[tool.rp-generate]` table or its keys, or the `generate` extra.
- Moving or renaming `rdf_persistence/model/rp_*.yaml` (keep.md), or splitting `rp_service.yaml`
  and `rp_wire.yaml` (that is `thematic-structure`, E-1).
- Moving the library's modules into themes (E-2 to E-5).
- Removing the shims in this change; they go one minor release later.
- Running containers in CI.
- New generator features, templates or LinkML generators.

---

## What Changes

- **BREAKING (tooling, one step):** every `rp-manifest.json` records the generator's files under
  `rdf_persistence_generation/`; a consumer runs `rp-generate` once after upgrading.
- `rdf_persistence/generation/` moves to `rdf_persistence_generation/` (code, `model/`,
  `generated/`, `templates/`, `lint.yaml`), with `py.typed`. The console script
  `rp-generate` points at `rdf_persistence_generation.cli:main`.
- **BREAKING (import path, no shim):** `rdf_persistence.generation` is gone (DEC-5); an import of
  it raises `ModuleNotFoundError` and the release notes name `rdf_persistence_generation`.
- No record moves: `technical-models` moved every record the library's testkit imports into
  `rdf_persistence.testkit.generated`; `ConstraintCase` and `ConstraintKind` stay in
  `rp_generation.yaml` and move with the conformance suite (design PD-1).
- `rdf_persistence/testkit/{freshness,conformance,roundtrip,strategies}.py` move to
  `rdf_persistence_generation/testkit/`; deprecation shims stay one minor release.
- F-4: `TOOLKIT_PACKAGE` and `PUBLIC_PACKAGE` go; the toolkit's schemas carry `python_package`
  and `rp.yaml` `public_package`; a hard check keeps them true.
- `pyproject.toml`: `module-name` lists both packages; the generator's `[[tool.rp-generate]]` entry
  points at its new schema and package.
- `.importlinter`: both root packages; a contract that the library never imports the generator;
  `works-without-the-generate-extra` re-pointed at the new package.
- Tests: `tests/unit/generation/` and the generator's testkit tests move to `tests/generator/unit/`;
  new `tests/generator/{feature,integration,e2e}`.
- `Makefile` and CI: lane `test-generator`, the library lanes leave out `tests/generator`, every
  path list (mypy, ruff, radon, xenon, `check-docs`, Sonar, `tests/changed.py`) names both packages.
- Docs: `architecture/generation.adoc`, `architecture/index.adoc`, `howto/adopt.adoc`,
  `develop/index.adoc`, `develop/testing.adoc`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-generation`: the generator is its own top-level package with its own test pyramid; the
  metamodel declares where its classes are imported from.
- `rp-package-boundaries`: the library never imports the generator; the wheel ships both packages,
  each typed.
- `rp-testkit`: the generator's test helpers move, with one release of deprecation shims.
- `rp-developer-checks`: CI gains the `test-generator` job.

## Impact

- Consumers: one `rp-generate` run after upgrading; `DeprecationWarning` on the old testkit paths
  until they change `pytest_plugins` and the four names' imports. Nothing changes for a running
  service.
- `thematic-structure` gets F-4 and a generator that imports the library one way only.
- `typescript-client`, `second-store`, `graphql-read-api`: any generator work they plan targets
  `rdf_persistence_generation`.
