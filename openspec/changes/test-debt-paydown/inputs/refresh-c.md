# Refresh C: PD-11 (not the moves), PD-12, PD-14 vs rules, agents/testing docs

Read-only refresh on develop 030f580f (2026-11-21), after the thematic restructure. Facts 9/10 and
`domain-survivors.md` were written on be129a0 (2026-11-17). Folder moves and `test_tenant_move`
are the other refresh's.

## 1. PD-11 under-the-floor items (still hold?)

### Class comment form: holds, and the counts grew
Forms today (`grep -rhoE "#\s*([A-Za-z ]*[Cc]lass(es)?:|one case per class)" tests`):

| Form | Hits | Files |
|---|---|---|
| `# Class:` | 44 | 9 (collaboration/*_adversarial 4 files, access/test_access_loading, test_access_annotate, api/test_workflow_routes_adversarial, testkit/test_guards, test_testkit_bootstrap) |
| `# equivalence class:` (lower case now) | 20 | 16 (tenancy 6, api 2, migrations 3, persistence 3, schema 1, access 1) |
| `# equivalence classes:` | 16 | 10 |
| `# One class:` | 8 | 6 (api/test_one_label_adversarial, test_route_class, test_problems, access/test_zitadel, files/test_s3_file_store ×2, persistence/test_fuseki_store ×2) |
| `# one class:` | 5 | 3 (generator/unit/test_generate_config, test_typescript_service_types_adversarial, test_generation_inputs ×3) |
| `# One case per class:` | 3 | 3 (api/test_negotiation, test_service_kit, test_router) |
| `# Classes:` | 0 | 0 |

So 52 to rewrite (was 39: `One class:`/`one class:` are new variants). Prose "one class" anywhere:
38 lines. `testing.adoc` still names no form (no "Class:" in the page); rule 6 is
`testing.adoc:56-57`.

### Plan-number docstrings/comments: holds; 113 hits split
`grep -rniE "equivalence class|\bstage [0-9]|\btask [0-9]+\.[0-9]+" tests --include=*.py` = 113:
- 40 `equivalence class(es)` comments (above);
- 73 stage/task hits: **56 docstring lines** (~54 docstrings; `test_iri_policy_minting.py:1,4`,
  `test_settings_howto_adversarial.py:1,3` hit twice), **15 comments**, **2 assert messages**
  (`tests/feature/test_observability.py:208, :240`).

Stage/task hits by folder (docstring / comment / other):
`tests/unit/api` 19/3/0; `tests/generator/unit` 11/2/0; `tests/unit` (root) 4/5/0;
`tests/unit/tenancy` 5/2/0; `tests/unit/iris` 3/1/0; `tests/unit/persistence` 3/1/0;
`tests/unit/testkit` 2/1/0; `tests/unit/core` 1; `events` 1; `messaging` 1; `tests/toy_service.py` 1;
`tests/e2e` 1; `tests/integration` 1; `tests/generator` (uml_library_stage2.py:5) 1;
`tests/generator/feature` 1; `tests/generator/integration` 1; `tests/feature` 0/0/2.

The 15 comments: `generator/unit/test_ext_pydantic_validators.py:330`, `test_extension_register.py:17`,
`unit/api/test_router.py:718`, `test_service_kit.py:393, :459`, `unit/iris/test_iri_policy_model.py:223`,
`unit/persistence/test_mapper_unit_of_work.py:576`, `unit/tenancy/test_tenancy.py:448, :688`,
`unit/test_no_old_module_paths.py:48, :52`, `unit/test_technical_split.py:297`,
`unit/test_theme_layout.py:302, :610`, `unit/testkit/test_fakes.py:70`.
Tasks.md 1.6's "42 docstrings and 39 comments" is stale: say 56 docstring lines, 15 + 2 other,
52 class comments. Note some hits are not plan numbers of *this* repo's archived plans but
fixture names in prose (`uml_library_stage2.py:5`, `test_uml_generate.py:5` "stage 1/2" of the UML
check): decide drop vs reword per line.

### Marker completeness: holds (no test)
`tests/unit/test_markers.py` checks rows (`:29`) and outside paths (`:35-56`); no test walks
`tests/**/test_*.py` against `_MARKERS_BY_DIR` (`tests/conftest.py:86-104`; `markers_for_path`
`:107`). Table now has `generator/{unit,feature,integration,e2e}/` rows first.

### Hypothesis under `-n 2`: holds
`test_markers.py:142-157`: `runpytest_subprocess("-p", "no:randomly", "-p", "no:cacheprovider")`,
no `-n`; `assert_outcomes(passed=1)`.

### `utc_now()` awareness: holds; path changed
`rdf_persistence/persistence/services/session.py:385-386` (`datetime.now(UTC)`). Used in
`api/entrypoints/sse.py`, `tenancy/services/{tenancy,tenant_dump,tenant_sweep}.py`,
`testkit/fakes.py`. No `utcoffset` assert in tests. Test goes to `tests/unit/persistence/`.

### `listing_shelf`: holds; path changed
`tests/unit/api/listing_shelf.py:13-19` (BOOKS with string genres), `:65`
`{**DUNE_BODY, "label": ..., "genre": ..., "authors": ...}`, `:66-67` `body["published"]`;
personas `"ada"` `:31, :38, :41`, `"rita"` `:72`, `"omar"` docstring only `:23`. `tests/unit/api/scene.py:36, 44, 48, 52, 55, 57`
uses `"ada"`/`"rita"`. `tests/toy_service.py` has no persona constants; imports `Genre` (`:34`),
uses `Genre.FICTION` (`:85`).

### Conftest constants: holds; locations changed
- `GENERATED`: now `tests/unit/conftest.py:19` (was `tests/unit/services/conftest`); 6 importers
  `from tests.unit.conftest import GENERATED`: `unit/api/test_iri_policy_minting.py`,
  `test_iri_policy_checks.py`, `test_documents.py`, `test_documents_strict.py`, `test_shacl.py`,
  `unit/tenancy/test_migration_runner.py`.
- `TOY`, `ROOT_SCHEMA`, `Breaker`: `tests/generator/unit/conftest.py:11, 12, 14` (generator tests
  moved from `tests/unit/generation/` to `tests/generator/unit/`). 16 files `from .conftest import`
  (golden.py `:25` itself, test_boundary_check, test_ext_pydantic_validators, test_ext_shacl_constraints,
  test_ext_typescript, test_generate_config, test_hard_check, test_lock, test_lock_adversarial,
  test_lock_step, test_openapi_components, test_partial_import, test_placement,
  test_python_package_rule, test_templates, test_typescript_service_types_adversarial). New
  constants imported the same way: `TOOLKIT_DOMAIN` (`:28`), `theme_package` (`:39`),
  `toolkit_domain_targets`. `TOY` is duplicated in `tests/generator/integration/conftest.py:14`.
  Target: `tests/generator/unit/golden.py` (or `terms.py`), not `tests/unit/generation/golden.py`.
- `make_book`/`make_tenant`: `tests/integration/api/conftest.py`, imported by
  `integration/api/test_router.py`, `test_negotiation.py`.
- `tests.conftest` imports (fine): `TESTS_ROOT_DIR` (test_pre_commit_config, test_lanes,
  test_markers, test_container_selection), `markers_for_path`, `load_container_plugin`
  (integration/e2e/perf/generator-e2e conftests).

### `TEST_DATA_DIR`, `load_text_file`: holds (dead)
`tests/conftest.py:40` (`tests/test_data` does not exist) and `:169-181`; no caller anywhere.

## 2. PD-12 mutation selection today

`setup.cfg [mutmut]` (mutmut 3.8.1, fnmatch: `*` spans `/`):
- `source_paths = rdf_persistence`; `do_not_mutate = rdf_persistence/*/generated/*` (matches
  `<theme>/domain/generated/*`).
- `only_mutate`: `rdf_persistence/*/domain/*`, `rdf_persistence/iris/services/iris.py`,
  `rdf_persistence/tenancy/services/tenant_move.py`.
- `pytest_add_cli_args_test_selection`: `tests/unit/core`, `tests/unit/files`, `tests/unit/iris`,
  `tests/unit/tenancy/test_tenant_move.py`; `pytest_add_cli_args = -p no:cacheprovider -q`.
- `Makefile:325-329` `mutation`: `uv run mutmut run`, `uv run mutmut results`.

Files mutated (non-generated, with code): `core/domain/base.py` (34), `exceptions.py` (207),
`media.py` (18), `sparql.py` (369), `sparql_parsing.py` (59, **new**), `files/domain/blob_keys.py`
(33), `iris/domain/layout.py` (109, **new**: graph/skolem/name helpers split out of iris.py),
`iris/services/iris.py` (641), `tenancy/services/tenant_move.py` (89). `access`, `collaboration`,
`provenance` `domain/__init__.py` are docstring-only (no mutants).
Was (be129a0): `only_mutate = rdf_persistence/domain/*`, tests `tests/unit/domain` +
`tests/unit/services/test_tenant_move.py`.

Gap: tests that kill iris mutants outside the selection do not count, e.g. Q's
`principal_template="{base}people/{sub}"` exists in `tests/unit/tenancy/test_iri_policy_guard_adversarial.py:301, :311`
and `tests/unit/api/test_iri_policy_wiring.py:138` but neither is selected: killing tests must sit
in `tests/unit/{core,files,iris}` or `test_tenant_move.py`.

### Groups: target today
Mutant numbers will shift (iris.py lost 288 lines and gained `layout.py`); use names/lines.

| Grp | Target now | State |
|---|---|---|
| A (5) | module wrappers `aggregate_iri`, `mint_aggregate_iri`, `mint_part_iri`, `loaded_graph_iri` | **gone** (thematic-structure PD-5; `tests/unit/iris/test_wrappers_removed.py:7-20`); also their 5 message mutants |
| B (20) | messages in `Iris.tenant` iris.py:465, `aggregate` :507, `_new_id` :444, `tenant_of_access` :607, `_require_distinct_graphs_of` :366-385, `_require_application_apart` :387-402; `root_of_graph` now `iris/domain/layout.py:51-56`; sparql `_literal` :57, `match_patterns` :177, `value_patterns` :212, `count` :259, `order_by` :266, `checked_group` :289, `term` :68, `_joined` :136, `_any_node_problem` :347 | exist; `MessageLimitExceeded.__init__` changed (`exceptions.py:202-207`, adds `command`): re-derive |
| C (9) | `KeyConflict.__init__` exceptions.py:52-56; `MigrationFailed.__init__` :144-150; `MessageLimitExceeded.__init__` :202-207 (+ new `command` attr mutants) | exist; no attribute test in `tests/unit/core/test_exceptions.py` |
| D (2), D' (1) | `tenant_resource_name` | **gone** (removed wrapper) |
| E | `_differences` iris.py:139-146 (`and` :142) | exists; `tests/unit/iris/test_iri_policy_effective.py` |
| F | `draw_id` iris.py:152-157 (`length or 0` :157) | exists (equivalent) |
| G | `_alternation` iris.py:166-167 | exists |
| H, H' | `_compile` iris.py:170-185 (backref :181, `seen.add` :183, `re.DOTALL` :185) | exist |
| I | `Iris.__init__` iris.py:210-217 (`deep=True` :217) | exists |
| J | `part_needs_type` iris.py:253-255 | exists; still no test (`grep part_needs_type tests` = audit report only) |
| K | `_require_distinct_graphs` iris.py:355-364 | exists |
| L, L' | `_require_distinct_graphs_of` iris.py:366-385 (`found`/`_belongs` :381-382) | exist |
| M | `_require_application_apart` iris.py:387-402 (:398-400) | exists |
| N | `_application_probes` iris.py:404-429 | exists; the per-kind shaped policies are now `tests/unit/iris/test_iris_application_adversarial.py:176-280` (`TENANT_SHAPED_AGGREGATE` :176, `REFUSED_AS_TENANT_SHAPED` :258-266, test :276) |
| O | `_probe_types` iris.py:431-433 | exists |
| P | `_reads_reserved` iris.py:557-561 | exists |
| Q | `principal` iris.py:543-549 (`**self._fixed.model_dump()` :546) | exists; killer must move into `tests/unit/iris/` |
| R | `tenant_move.check_graphs` `tenancy/services/tenant_move.py:67-89` (`is_loaded_graph(tenant, graph)` :85) | exists |
| S | `_string` `core/domain/sparql.py:49-54` (`_AFTER_BACKSLASH` sub :53) | exists |
| T | `checked_group` sparql.py:289-311 (`_parsed(text, template)` :303; `_parsed` :314) | exists |

Net from the old plan: kill list 40 → 39 (D' gone); equivalents 32 → 25 (A 5, D 2 gone); 38
message mutants → 33 (5 in removed wrappers). New, unknown: `layout.py`, `sparql_parsing.py`,
`MessageLimitExceeded.command`. The 3.1 re-run decides.

Killing-test paths: `tests/unit/domain/` no longer exists. `test_exceptions.py`, `test_sparql.py`,
`test_sparql_parsing.py` → `tests/unit/core/`; `test_iris*.py`, `test_iri_policy_*.py`,
`test_layout.py` → `tests/unit/iris/`; `test_tenant_move.py` → `tests/unit/tenancy/` (already in
its theme; tenant_move.py is now `tenancy/services`, so the old "move to domain" reason is gone,
and its `setup.cfg` line stays while only that tenancy file is selected).

### Proposed split (disjoint test files)
- **3.2 core + files + tenancy + iris layout:** `tests/unit/core/test_exceptions.py` (C + new
  `command`), `tests/unit/core/test_sparql.py`, `test_sparql_parsing.py` (S, T, new
  sparql_parsing), `tests/unit/files/test_blob_keys.py` (any blob_keys), `tests/unit/tenancy/test_tenant_move.py`
  (R), `tests/unit/iris/test_layout.py` (layout.py survivors). Old count ~13 + new files.
- **3.3 iris policy (`iris/services/iris.py`):** `tests/unit/iris/test_iris.py`, `test_iris_policy.py`,
  `test_iris_application*.py`, `test_iri_policy_*.py` (E in `test_iri_policy_effective.py`): E, G,
  H, H', I, J, K, L, M, N (7), O, P, Q; L' timeboxed. Old count 27 + L'.
- Uneven (≈13 vs 28). If the re-run keeps it so, split 3.3 by test file instead of adding a
  third task: 3.3a mint/match (E, G, H, H', I, J, P, Q: 12 → `test_iris.py`, `test_iris_policy.py`,
  `test_iri_policy_effective.py`), 3.3b policy checks (K, L, L', M, N, O: 14 + L' →
  `test_iris_application_adversarial.py`, `test_iri_policy_model_adversarial.py`).

### Naming
`inputs/survivors-before.md` still fits as 3.1's output name. `domain-survivors.md`'s title
("not killed by tests/unit/domain") and PD-12/stage 3's "Domain survivors"/"domain mutation" no
longer describe the selection (domain of every theme + iris policy + tenant move); say "mutation
selection (setup.cfg [mutmut])" and head `survivors-before.md` with the commit and selection.

## 3. PD-14 / approach vs repository rules

| Rule | Says | Conflicts with design "Algorithm / approach" |
|---|---|---|
| P-0013 (`docs/rules/P-0013 ...md:9-11`, 2026-11-20) | stage PR merged into develop once CI is green, without waiting, `--admin` where a review blocks; never on red/missing check | design `:146-148` "one branch, one PR at the end"; proposal Appetite (`proposal.md:14-15`) and DEC-2 (`:50-51`) "one pull request". P-0013 presumes a PR per stage; its CI-green gate matches PD-14's intent. Later than DEC-2/OQ-1 (11-17); "for every EPIC: yes to 1" |
| `agents.adoc:154` | "Each stage ends in one PR into develop, merged only on green CI" | same conflict; stage PRs are the repo default |
| P-0002 | rebase on develop before each PR (parallel sessions) | with stage PRs, rebase 3 times; with one PR after a 3-stage run, a long-lived branch against a moving develop (thematic restructure just landed) |
| P-0015 (2026-11-20) | worktrees under git-ignored `.worktrees/`, not beside the repo | design `:147` `git worktree add temp/wt/<task>`: change to `.worktrees/<task>` |
| `agents.adoc:90-91` | a builder gets its own worktree only for overlapping parallel work or when another session holds the checkout | design gives every builder a worktree although files are disjoint; justify (parallel `make test-changed` runs) or drop |
| P-0016 (PR #233, 2026-11-21) | one session through every stage, the docs stage and the archive | compatible (3.5 ends in archive); no docs stage named in tasks.md: say if none is owed |
| P-0004 | before the last merge, reconcile proposal.md (table, What Changes, deltas) | not in tasks 3.5; add |
| P-0005 | MEDIUM+: one L2+L3 pass per stage, full review (L1, L2, L3 apart, L4+L5 one) once at the end | tasks 1.7, 2.6, 3.5 follow it (LARGE) |

Lead cherry-picking from builder worktrees conflicts with no rule.

## 4. What the PLAN must follow (agents.adoc, testing.adoc)

- Gates (`agents.adoc:87-125`): builder `make test-changed check-quality` (`test-fast` after
  domain/port); lead `make check-all` + `make test-containers` once per stage before the PR and
  again after the fix pass, never `make test` beside `check-all`; `make check-generated` after a
  schema commit (none planned).
- Review (`:132-150`): one L2+L3 pass per stage; full review once at the end, L1/L2/L3 apart,
  L4+L5 one; adversarial tester right after the riskiest task; checker reads the lead's
  `check-all`, does not rerun; accepted findings into `design.md` before the fix, one fixer.
- Re-index GitNexus at the start of each stage (`:166-172`), and before impact on symbols moved
  in the stage (stage 1 moves many test files).
- Briefs (`:50-59`): standing rules, report shape (files, tests, each target with time and
  count), tools section, builder skips impact.
- Durations table kept current (`:173-175`, `testing.adoc:128-130`); CI runs `make test-unit-ci`
  in 8 shards balanced by `.test_durations` (`testing.adoc:85-87`): after PD-8/PD-11 moves, run
  `make test-durations` if shards drift; run slow tests locally before a PR.
- `make refresh-map` (Makefile:123) re-keys `tests/audit/scenario-map.csv` (4844 lines; no
  `tests/unit/domain|services|entrypoints|generation` paths left) against `BASE`.
- testing.adoc rule numbering: 1-12 (`:13-75`); rule 6 `:56-57` is where the class form goes.
  DEC-3 cites "rule 9 forbids asserting message text": rule 9 here is Gherkin (`:62-63`); no rule
  in `testing.adoc` forbids message text. Cite its true source or add it. (`:102` cites a "rule
  14" the page does not have.)
