# Design: typescript-toolkit-modules

> Derives from: EPIC `typescript-toolkit-modules` (proposal.md, DEC-1 to DEC-6). Facts:
> `inputs/seed.md`; the owner's answers and the planner's choices: `inputs/qa.md`.

## Context

`TYPESCRIPT_STEP` is `Step("typescript", _write_typescript, writes=True)` (`steps.py`).
`_write_typescript(run)` calls `typescript.render(run.schema_path, folder=<own folder>,
owners=_typescript_owners(run))`, where the owners are the packages of the run's other targets that
set `typescript` (from `run.targets`, flags applied; `()` on a flags-only run). `render` builds
`generator.modules()`, drops and re-points the modules an owner writes (`_imported_from_owners`,
`_importing`, `_specifier`), then `_with_served` adds the served schemas' modules (built once per
process by `_served_modules`), merges the served schemas' own types into `rp_service.ts`
(`_merged`), points imports of a served schema at `rp_service` (`_pointing_at_merged`) and renders
the files; `with_index` adds `index.ts`. The toolkit's metamodel modules have `python_package` values
under `rdf_persistence.*`, so no project target owns them and every TypeScript target writes them.
`config.read_targets` validates each `[[tool.rp-generate]]` row into a `GenerationTarget`
(generated from `rdf_persistence_generation/model/rp_generation.yaml`); nothing checks rows against
each other except `_refuse_unusable` (flags with several rows). `manifest.current_inputs` lists the
target's schema closure, the served schemas when `typescript` is set, and the generator's files.

## Decisions

- **PD-1 The key.** `rp_generation.yaml`: a new slot `toolkit_typescript` on `GenerationTarget`
  (after `typescript`), `title: Toolkit TypeScript owner`, `range: boolean`, `ifabsent: "false"`,
  `alias: toolkit-typescript`, `slot_uri: rp:toolkitTypescript`, no `cli_flag` annotation (no-go);
  description: "Whether this entry's TypeScript folder holds the toolkit's shared TypeScript modules,
  which the project's other TypeScript entries import (TOML key `toolkit-typescript`). Required on
  exactly one entry when two or more set `typescript`; changes nothing when one does." The lead runs
  `make generate` (task 1.1) so `GenerationTarget.toolkit_typescript` exists.
- **PD-2 The cross-entry check (DEC-3).** `config._refuse_toolkit_owner(targets, project)`, called by
  `_toml_entries` after the rows validate, raises `ConfigError` (each entry named by its `schema` key,
  in file order):
  - an entry with `toolkit-typescript = true` and no `typescript`: `"<schema>: toolkit-typescript
    needs typescript on the same [[tool.rp-generate]] entry in <project>"`;
  - two or more entries set `typescript` and none sets the key: `"<a>, <b> write TypeScript in
    <project>: set toolkit-typescript = true on the one whose folder holds the toolkit's types
    (rp_core.ts, rp_service.ts, ...); the others import them from it"`;
  - more than one sets it: `"toolkit-typescript is set on <a>, <b> in <project>: set it on one"`;
  - two entries set the same `typescript` folder (compared as normalised relative paths):
    `"<a>, <b> write TypeScript into the same folder <folder> in <project>: give each its own"`.
    Reason: each entry's manifest owns the files it wrote, so on a regeneration one entry's stale
    removal would delete a file the other just wrote (`pipeline._publish`).
  Every reader of `read_targets` (the CLI, the freshness plugin) refuses the same way; the CLI
  already turns `ConfigError` into its exit with the message, before any step runs.
- **PD-3 The shared set (DEC-4).** `typescript._shared_modules() -> tuple[TsModule, ...]`, cached
  like `_served_modules`, keyed on `(METAMODEL, tuple(SERVED_SCHEMAS))`: the modules of
  `_generator(METAMODEL).modules()` (the metamodel's closure with classes or enums: today `rp_access`,
  `rp_collections`, `rp_core`, `rp_discussion`, `rp_files`, `rp_provenance`, `rp_tenancy`,
  `rp_workflow`) and the served modules `_served_modules` yields that are not served schemas
  themselves. `_shared_names()` is their names, the served schemas' names and `SERVICE_MODULE`.
  When both sources yield a module of the same name (`rp_core`, `rp_access`, `rp_tenancy`), the
  metamodel's render wins: the metamodel modules are taken first and the served ones are added by
  `setdefault` by name. Reason: the metamodel root is the module's own closure, and it is the render
  a target that imports the metamodel writes today (TC-2 pins it against the committed files).
- **PD-4 The owner of a run.** `steps._toolkit_folder(run) -> Path | None`: `None` when fewer than
  two of `run.targets` set `typescript` (DEC-3: one target, or a flags-only run, is unchanged);
  otherwise `Path(t.typescript)` of the one target with `toolkit_typescript`. PD-2 guarantees one
  for every `Run` built from `read_targets`; a `Run` built another way (a test, a caller of the
  pipeline) may hold two or more TypeScript targets and no owner, or several: then `_toolkit_folder`
  returns `None` and every target copies, as today. Reason: the refusal belongs to the configuration
  reader, which runs before any step; a step never raises a configuration error.
  `_write_typescript` passes the folder and `run.target.toolkit_typescript` as
  `typescript.render(..., toolkit=<folder>, owns_toolkit=<flag>)`.
- **PD-5 Render.** `render(schema_path, *, folder=None, owners=None, toolkit: Path | None = None,
  owns_toolkit: bool = False)`; `toolkit=None` keeps today's path exactly. Owner and importer are told
  apart by `owns_toolkit` (the run's own `toolkit_typescript`), which states the role directly rather
  than inferring it from paths; entries never share a folder (PD-2 refuses it). After the #371 drop
  (unchanged):
  - **owner** (`toolkit` set and `owns_toolkit`): the modules gain every module of `_shared_modules()` whose name
    they lack (`setdefault` by name: a module the target's own closure renders keeps its own render),
    then `_with_served` as today. The owner's files are today's plus any metamodel module its schema
    does not import.
  - **importer** (`toolkit` set and not `owns_toolkit`): drop every module whose name is in
    `_shared_names()`; point served-schema imports at `SERVICE_MODULE` (`_pointing_at_merged`); then
    re-point each import whose `module` is in `_shared_names()` to
    `_specifier(toolkit, module, folder)` (PD-4 of consumer-friction: `posixpath.relpath`, a leading
    `./` when needed; imports stay sorted by `module`); render with `_file`, no `_with_served`;
    `with_index` exports only what was written.
  The reserved-name check (`_clashes`) runs for every target, as today.
- **PD-6 Manifest inputs.** `manifest.current_inputs`: a target with `typescript` and
  `toolkit_typescript` also lists the metamodel's files (`_schema_files(METAMODEL)`), so a change to a
  metamodel module it writes but does not import is a stale input. An importer keeps the served
  schemas as inputs (its imports name their types).
- **PD-7 Stale copies.** No code: an importer's earlier `rp_core.ts` and the like are outputs of its
  previous manifest and not of this run, so `pipeline._remove_stale` deletes them (or keeps a
  hand-edited one with a problem), as for #371.
- **PD-8 The toy.** `tests/fixtures/library/pyproject.toml`: the domain entry gets
  `toolkit-typescript = true`, with a comment naming this change, in task 1.1, before PD-2's check
  exists, so no toy-based test sees an invalid table. Once render reads the key (task 1.3), `make
  generate` (task 1.4) rewrites the value
  and technical trees (each loses `rp_access.ts`, `rp_core.ts`, `rp_service.ts`, `rp_tenancy.ts`);
  the domain tree is expected unchanged, since its closure already holds the whole shared set
  (task 1.4 checks it; TC-2 checks the renders themselves, RISK-2). `TOY_TS` in the `Makefile` is unchanged (wildcards).
- **PD-9 Docs.** `architecture/generation.adoc` *Imports between targets*: a paragraph on the owner of
  the toolkit's TypeScript, the shared set, DEC-5, and the refusals. `user-manual/generate.adoc`: the
  key in the keys table; the `typescript` output row ("...; in a project with several TypeScript
  entries, the toolkit's modules only in the entry with `toolkit-typescript`"); the example
  `pyproject.toml` with two TypeScript entries. `CHANGELOG.md` `[Unreleased]` *BREAKING* with the
  migration note: "a project with two or more TypeScript entries sets `toolkit-typescript = true` on
  one; until it does, `rp-generate` refuses the table, and so does every test session that loads the
  freshness plugin (it reads the same table), so set the key before running the tests. The other
  entries no longer hold `rp_core.ts`, `rp_service.ts` and the other toolkit modules: import those
  types (`TenantSummary`, `Problem`, `InUseProblem`, a metamodel type) from that entry's folder. A
  project upgrading from before the release that stopped copying a module another entry owns (#371)
  also moves those imports to the owning entry's folder."

## Algorithm / approach

Worked example (the toy after PD-8). Targets with `typescript`: domain (`web/src/domain/generated`,
owner), value (`web/src/domain/generated/values`), technical (`web/src/services/generated`).

- The domain run: `owns_toolkit` (its entry sets the key) → owner. Its closure already renders the eight metamodel
  modules; `_shared_modules()` adds none; `_with_served` writes `rp_service.ts`. Files unchanged.
- The value run: importer. `generator.modules()` = `loan_checks`, `rp_core`, `rp_access`,
  `rp_tenancy`, ... → the shared ones are dropped, `loan_checks` stays. Its import of `rp_core`
  becomes `relpath("web/src/domain/generated/rp_core", "web/src/domain/generated/values")` =
  `"../rp_core"`. Files: `loan_checks.ts`, `index.ts`.
- The technical run: importer; #371 already drops `loan_checks` (owner: value target). Its imports of
  toolkit types become `"../../domain/generated/rp_<x>"`, of `rp_service` types
  `"../../domain/generated/rp_service"`. Files: `loan_checks_response.ts`, `index.ts`.

## Error matrix

| Input / state | Behaviour |
|---|---|
| One entry sets `typescript`, key absent or true | `_toolkit_folder` → `None`; today's files (DEC-3) |
| Flags-only run (no table) | `run.targets == ()` → `None`; today's files |
| A `Run` not built by `read_targets` with two or more TypeScript targets and no owner, or several | `_toolkit_folder` → `None`; every target copies, as today; no error from the step (PD-4) |
| Two entries set the same `typescript` folder | `ConfigError` before any step, naming both (PD-2) |
| Two entries set `typescript`, key on none | `ConfigError` before any step (PD-2), names both, says what to set |
| Key on two entries | `ConfigError`, names both |
| Key on an entry without `typescript` | `ConfigError`, names it |
| Key on an entry with `typescript`, one TypeScript entry | accepted, no effect on files; metamodel files become manifest inputs (PD-6) |
| Owner's schema does not import a metamodel module an importer uses | the owner writes it anyway (DEC-4) |
| Importer imports a technical toolkit module outside the shared set | not in `_shared_names()` → written by the importer, as before (DEC-5) |
| Importer's previous copies | removed as stale; a hand-edited one kept with a problem (PD-7) |
| Owner's folder nested under the importer's, or the reverse | `relpath` yields `./...` or `../...` (consumer-friction PD-4, TC-4 there) |
| A project module named like a shared module | a served name is refused by `_clashes`, as today; a module named like a metamodel module (`rp_core`) already collides in the schema closure, which keys modules by name, so it is not designed for here; accepted |
| Key added or moved later | `pyproject.toml` is not a manifest input: `rp-generate --check` misses it, `make check-generated` sees it (accepted, as in consumer-friction) |
| Owner generated after an importer in the same run | the importer's import names a file the owner writes in that run; `tsc` in CI checks it (TC-4) |

## Anti-patterns

- Telling toolkit modules apart by `python_package` prefix or folder in the importer: the shared set is
  the fixed set of PD-3, nothing else.
- Loading the other targets' schemas to compute what the owner writes.
- A CLI flag or environment variable for the owner.

## Test plan

| TC | Scenario | Proof | Tier / lane |
|---|---|---|---|
| TC-1 | spec "two TypeScript targets and an owner" | `typescript.render(tech_schema, folder=web/src/services/generated, owners=..., toolkit=web/src/domain/generated)` on the toy: no `rp_core.ts`, `rp_service.ts`, `rp_access.ts`, `rp_tenancy.ts`; `loan_checks_response.ts` imports `from "../../domain/generated/rp_service"` (and the metamodel types from `../../domain/generated/rp_<x>`); `index.ts` exports none of them | generator unit, new `tests/generator/unit/test_typescript_toolkit_owner.py` |
| TC-2 | same, RISK-2, PD-3 | (a) owner render adds a metamodel module the owner's schema does not import (the toy's value schema rendered as owner gains `rp_collections.ts`); (b) for each module `m` of `_shared_modules()` except the merged served module, `_file(m).text` equals the toy's committed `web/src/domain/generated/<m>.ts`, and the owner render's `rp_service.ts` equals the committed one, so a render from `rp.yaml` or the served schemas is proved equal to what a consumer's closure writes | generator unit |
| TC-3 | same | the toy's three trees equal the committed files after PD-8 (`run_toy` per target, `assert_matches_toy`); the domain tree is unchanged by this change | generator unit |
| TC-4 | same | `make typecheck-ts` compiles the three toy folders together; a wrong specifier fails with `TS2307`, a missing name `TS2305`. Needs Node: CI "types" job | CI `make check-types` |
| TC-5 | spec "one TypeScript target", PD-4, PD-5 | `render(..., toolkit=None)` equals today's output for the domain schema; `_toolkit_folder` is `None` for one TypeScript target with the key, for `targets=()`, for a `Run` built by hand with two TypeScript targets and no owner, and for one built by hand with two owners | generator unit |
| TC-6 | spec "several and no owner", "two owners", "the key on an entry without TypeScript", "two entries share a TypeScript folder" | `read_targets` on four temporary `pyproject.toml` files raises `ConfigError` with the messages of PD-2 | generator unit, `tests/generator/unit/test_generate_config.py` |
| TC-7 | spec "the old copies are removed" | on a `toy_copy`: run `rp-generate` with only the value entry setting `typescript` (the domain and technical entries' `typescript` and the key removed), so the value target, the one TypeScript target, writes `rp_core.ts` into `web/src/domain/generated/values/`; restore the toy's `pyproject.toml` and run again; assert that file is gone and `loan_checks.ts` is there | generator integration, `tests/generator/integration/`, `make test-generator` |
| TC-8 | PD-6 | `current_inputs` of a target with the key lists `rdf_persistence/model/rp_collections.yaml` | generator unit |
| TC-9 | gate | `make check-generated` clean for the toy and the toolkit | `make check-all` |

## Risks

- **RISK-1 (DEC-6) a consumer's frontend breaks on regeneration.** Every import of a toolkit type from
  an importer's folder fails to compile; likelihood high for a consumer with several TypeScript
  targets (a consumer has four today), impact low (`tsc` names each line). On upgrade, before the key
  is set, the refusal also stops every test session of the consumer, since the freshness plugin and
  `steps.py` read the same table through `read_targets`: impact medium (nothing runs until the key is
  set), likelihood certain for such a project. Mitigation: the `ConfigError` hint says what to set,
  the CHANGELOG *BREAKING* line says to set the key before running the tests and gives both
  migrations (PD-9), the PR names the consumer (D-12).
- **RISK-2 the owner's render of a toolkit module differs from the copies.** A module rendered from
  the metamodel root could differ from one rendered from a consumer's closure. Mitigation: TC-3
  requires the toy's domain tree unchanged (it holds every metamodel module rendered from the
  consumer's closure) and TC-2(b) compares each shared module's render with the committed file;
  `setdefault` keeps the owner's own render first; a difference fails task 1.3 (TC-2) or task 1.4
  (the domain tree) and is reported, not patched over.
- **RISK-3 the toolkit's own trees change.** No target of the toolkit's `pyproject.toml` sets
  `typescript`, so `_toolkit_folder` is `None` there; the `rp-manifest.json` hashes and
  `rp_generation`'s own artefacts change (new slot, generator files are inputs). Mitigation: task 1.1
  accepts only those diffs and reports any other.
- **RISK-4 a conflict with the parallel changes.** `consumer-write-rules` touches the schema loader
  and `narrowed-slot-override` the Python step; neither touches `typescript.py`, `steps.py`'s
  TypeScript step or `config.py`. Mitigation: rebase before the PR (P-0002); conflicts only in
  `openspec/changes/README.md` or `CHANGELOG.md` are resolved by whichever merges second.

- **RISK-5 stale trees stop the builders' tests.** The generator's files are manifest inputs of the
  toolkit and the toy (`pytest.ini` `rp_generate_projects`), so a code edit in
  `rdf_persistence_generation/` stops every test session until `make generate` runs. Mitigation:
  1.2 and 1.3 each in a worktree of its own, where `make generate` is not shared (tasks.md header);
  the lead checks the generated diffs against RISK-3.

## Delivery decisions

Taken by the epic-session lead (R-0007), 2026-11-27; the owner may overrule any of them.

- **D-1 Impact of `_toml_entries` is HIGH, by design.** GitNexus (index behind HEAD, so a floor)
  rates `config._toml_entries` HIGH: every reader of `read_targets` (the CLI, the freshness plugin,
  the `steps` helpers, the conformance testkit) is reached. That is PD-2's intended effect ("every
  reader refuses the same way") and RISK-1's accepted mitigation, signed off with the scenarios
  (`evidence/signoff.md`); no new risk, so the stage proceeds and the PR names it. Before the PR,
  `detect_changes` against `origin/develop` rates the stage critical: 14 symbols, 27 flows, every
  one through `read_targets`/`_toml_entries` (the conformance testkit's `run` and `used_kinds`)
  or `current_inputs` (`build_manifest`), the same designed reach; nothing outside it.
- **D-2 No test seed in the lead's worktree.** Per P-0022 the seed feeds only `make test-changed` in
  the worktree it runs in. Tasks 1.2 and 1.3 run in worktrees of their own (RISK-5), where a seed
  would go stale at the builder's first generator edit; their task gate falls back to its own lane.
  The shaping session's seed of this worktree was stopped and is void. Later tasks here (1.5, 1.6)
  are small; `make check-all` runs every test before the PR.
- **D-3 `make install` in this worktree.** Its environment lacked the `generate` extra
  (`rp-generate needs LinkML's generators`), so the lead ran `make install` (`uv sync --all-extras`)
  before task 1.1's `make generate`.
- **D-4 PD-2's "normalised paths" is kept as a guard.** The builder of 1.2 found that the
  `relative_path` pattern already refuses `.` and `..` segments, so two accepted spellings of one
  folder cannot reach the check; `web/./a` is refused earlier, as an invalid `typescript` value. The
  check keeps `posixpath.normpath` (harmless) and the test table pins both behaviours. PD-2 and the
  spec scenario stay as written: they hold, the example is merely refused one step earlier.
- **D-5 Tasks 1.3 and 1.4 share one commit.** The regenerated toy trees are what 1.3's tests
  assert, so a 1.3 commit without them would be red. The lead applied 1.3's source and test diff,
  ran `make generate` in this worktree and got the builder's toy diff exactly; the domain tree is
  byte-identical (RISK-2) and `make typecheck-ts` passes locally (TC-4).
- **D-6 Narrower task gates for 1.5 and 1.6.** `make test-changed` never runs the integration lane,
  so 1.5's gate is its own file (`uv run pytest`) and `make check-quality`; 1.6's is
  `make check-docs` (its Accept). With no seed, `make test-changed` would rerun the whole fast lane
  (about 20 minutes) for a test-only and a docs-only task; `make check-all` runs every lane before
  the PR.
- **D-7 Review findings (one pass L2+L3, PR #425).** Accepted, re-labelled Critical:
  - **F1 (W1)** — the spec scenario "two TypeScript targets and an owner" is not proved through
    `render`: no toy importer imports a toolkit type, so TC-1 as written (`loan_checks_response.ts`
    imports `../../domain/generated/rp_service`) cannot hold on the toy, and the re-pointing is
    tested only on a hand-built module through a private helper. Reason for the re-label: it is
    the EPIC's core behaviour, unverified. Fix: a `render(..., toolkit=...)` test on a temporary
    schema whose class uses a metamodel type and a served type, asserting the relative specifiers,
    no shared file and an `index.ts` without them. TC-1 is proved that way, not on the toy.
  - **F6 (S6)** — `user-manual/generate.adoc` said a second entry is "only needed when a second
    folder receives TypeScript", which is untrue (every schema target needs its own entry). Reason:
    a false statement in a user-facing page. Light chore, lead-fixed.

  Under the floor (not fixed):
  - W2 — DEC-5 (a toolkit module outside the shared set is still copied) has no test of its own;
    it is the default path (a name not in `_shared_names()` is not dropped).
  - S3 — `_importing_toolkit` repeats the drop, re-point and sort of `_importing` (L5, not in the
    SMALL set).
  - S4 — `render` with `toolkit` and no `folder` quietly copies; the step always passes a folder.
  - S5 — `assert _typescript_owners(run) is not None` in `test_typescript_toolkit_owner.py` cannot
    fail.

- **D-8 A flaky tooling test after the rebase.** `make check-all` on the rebased head (a19e700c,
  864 s) failed once, in `tests/unit/tooling/test_lanes.py::test_on_ci_pytest_runs_unqueued_with_the_workers_counted_by_make`
  (`-n 15` against `-n 16`). This change touches no Makefile or tooling; `PYTEST_N` recomputes the
  worker count from free memory at each expansion, so two expansions differ under load. The test
  passes alone; filed as #432, not fixed here. The other lanes of that run passed (unit coverage
  96.28 %); CI is the merge check.

## Lanes for moved or rewritten tests

Rewritten: none. The toy's committed value and technical TypeScript trees change (PD-8); the tests that
compare them (`test_typescript_imports.py` TC-1/TC-2 of consumer-friction, `test_ext_typescript.py`
goldens) keep running in the generator unit lane and are updated only by `make generate`, never by hand.
`test_a_toy_generation_writes_rp_service_ts` (`test_typescript_service_types_adversarial.py`) expects
one `rp_service.ts` per TypeScript target; after PD-8 it expects one in the owner's folder. Task 1.4
rewrites that assertion; the test stays in the generator unit lane (marked `slow`) and still proves the
served types are written, now once per project.
