# Refresh B: PD-8, PD-11, test_tenant_move, the guard (develop 030f580f, 2026-11-21)

Read-only fact refresh for the re-plan. Paths are today's (thematic layout). Probe record:
`inputs/probes/cross_imports.out` (overwritten: 108 statements, 43 source modules).

## 1. PD-8 cross-test imports

### What the probe misses (add to the count)

- **Non-test importer:** `tests/unit/sparql_threads.py:36` `from tests.unit.tenancy.test_migrate_dataset import STAMPS, dataset, stamp` ✱ (unit root, run as `-m`).
- **Module-object imports** (`from tests.x import test_y`; the probe's regex looks at the module, not the names):
  - `tests/unit/collaboration/test_collaboration_workflow_adversarial.py:78` `import test_collaboration_workflow as built`, rebinding 7 fixtures `ada, bob, books, now, plain, session, store` (`:105-114`);
  - `tests/unit/events/test_relay_adversarial.py:25` `import test_relay`; `world = test_relay.world` (`:43`, a fixture);
  - `tests/unit/tenancy/test_tenant_sweep_adversarial.py:17` `import test_tenant_sweep as worked`; `world = worked.world` (`:29`, a fixture);
  - `tests/unit/test_no_old_module_paths.py:17` `import test_theme_layout`; monkeypatches `TURNED_ON` on it (`:252`).
- Relative imports in `tests/generator/unit/` (`from .test_lock`, `.test_freshness`, `.test_generate_cli`, `.test_hard_check`, `.test_boundary_check`): the probe resolves them; the guard must too.
- No helper or conftest imports a test module apart from `sparql_threads.py` (grep of `tests/`).
- Total: 108 + 1 + 4 = **113 statements, 43 source modules** (the module-object ones add no new source).

### Fixtures imported by name (go to a conftest)

`test_tenant_dump`: `stamped`, `aged`, `chains` (`:301`, `:464`, `:430`; used by
`test_restore_across_versions_adversarial.py:31`, `# noqa: F401 (the fixtures)`).
`test_migrate_dataset`: `lib_chain`, `three`, `toolkit_chain` (`:71`, `:79`, `:89`; used by
`test_migrate_dataset_adversarial.py:22`). Plus the three rebinding forms above
(`world` x2, the 7 workflow fixtures). `tests/unit/tenancy/` and `tests/unit/events/` have no
`conftest.py` today; `tests/unit/collaboration/conftest.py` exists.

### Existing helper modules (all exist)

`tests/toy.py`, `tests/toy_service.py`, `tests/unit/builders.py`, `tests/unit/conftest.py` (`GENERATED`),
`tests/unit/import_contracts.py`, `tests/unit/api/{scene,listing_shelf,tenant_requests}.py`,
`tests/unit/collaboration/collaboration_data.py`, `tests/unit/tenancy/migration_helpers.py` (already
imported by `tests/integration/store/test_migration_requests.py`: cross-tier today),
`tests/generator/unit/{golden,terms}.py`, `tests/e2e/world.py`, `tests/integration/store/sessions.py`,
`tests/integration/tenancy/file_stores.py`. No `tests/unit/{services,entrypoints,generation,domain}/`
any more: the old table's homes there are void.

### Rule as adapted

Constants/builders → a helper beside their users; fixtures → that folder's `conftest.py`; a helper
used across **tiers** → `tests/` root; used across **themes of one tier** → that tier's root
(`tests/unit/`, precedent `builders.py`). ✱ = imported from another tier or theme folder.

### Table (43 source modules)

| Source test module | Importers (stmts: folders) | Home |
|---|---|---|
| `unit/tenancy/test_tenant_sweep` ✱ | 17: feature, integration/tenancy, unit/{api,events,messaging,persistence,provenance,tenancy} (+ module import) | `tests/tenancy_world.py` (new): `make_world`, `CREATOR`, `book`, `TURTLE`, `BOOK_TYPE`, `FILE_KEY`, clock consts, `Events`/`EventFiles`, `FLAT`, `ALL_QUADS`, `OWNED_BY`; fixture `world` → `tests/unit/tenancy/conftest.py` (new) |
| `unit/tenancy/test_tenant_dump` ✱, `unit/tenancy/test_pending_mark` ✱ | 7 + 2: feature, integration/tenancy, unit/tenancy | `tests/dump_helpers.py` (new: `BASE_STAMPS`, `TOY_CHAINS`, `RESTORER`, `VIEW`, `MANIFEST`, builders); fixtures `stamped`, `aged`, `chains` → `tests/unit/tenancy/conftest.py`; `PLUMBING`, `three_commits` → `tests/unit/tenancy/tenancy_helpers.py` |
| `unit/tenancy/test_session_activity` ✱, `unit/persistence/test_session_activity_adversarial` ✱, `unit/persistence/test_session_unique_keys` ✱, `unit/provenance/test_activity_shape` ✱ | 11 + 1 + 3 + 1: unit/{api,collaboration,messaging,persistence,provenance,tenancy} | `tests/unit/activity_helpers.py` (new, unit root beside `builders.py`) |
| `unit/events/test_relay` ✱ | 2: feature, unit/events (+ module import, fixture `world`) | `tests/relay_helpers.py` (new); fixture `world` → `tests/unit/events/conftest.py` (new) |
| `unit/api/test_events_route` ✱ | 1: feature (7 names) | `tests/events_follow.py` (new): `listening`, `mount`, `replace`, `reshape_grants`, `with_carol`, `another_book`, `events_of`, with `opening`, `drained` (#213; these two are not imported elsewhere today, they move as the route tests' companions) |
| `unit/api/test_service_kit` ✱ | 4: feature, unit/api | `tests/toy_service.py` (`made`, `installed`, `A_UUID`) |
| `unit/api/test_documents` ✱ | 2: unit/{api,persistence} | `tests/toy.py` (`BOOK`, `BOOK_JSON`, `encoded`) |
| `unit/api/test_router` | 1: unit/api | `tests/unit/api/scene.py` (`everyone_has_a_role`, made public) |
| `unit/api/test_iri_policy_checks` | 1: unit/api | `tests/unit/api/iri_policy_helpers.py` (new) |
| `unit/core/test_sparql_parsing` ✱ | 1: unit/api (`RecordingLock`) | `tests/unit/builders.py` |
| `unit/tenancy/test_migration_runner` ✱, `unit/tenancy/test_migrate_dataset` ✱ | 2 + 1 (+ `sparql_threads.py`): integration/store, unit/tenancy, unit root | `tests/migration_helpers.py` (move the existing `tests/unit/tenancy/migration_helpers.py` there: already cross-tier); fixtures `lib_chain`, `three`, `toolkit_chain` → `tests/unit/tenancy/conftest.py` |
| `unit/tenancy/test_tenancy`, `test_tenancy_stores` | 1 + 1: unit/tenancy | `tests/unit/tenancy/tenancy_helpers.py` (new) |
| `unit/migrations/test_migration_chain`, `test_migration_files` | 1 + 1: unit/migrations | `tests/unit/migrations/migration_steps.py` (new) |
| `unit/persistence/test_loading` | 1: unit/persistence (`AGGREGATE`, `TENANT`) | `tests/unit/persistence/loading_helpers.py` (new) |
| `unit/messaging/test_messagebus`, `test_messagebus_wiring` | 1 + 1: unit/messaging | `tests/unit/messaging/messagebus_helpers.py` (new) |
| `unit/collaboration/test_collaboration_{cascade,collections,collections_adversarial,discussion,workflow,workflow_adversarial,nesting_cycles}`, `test_write_guards` | 5+4+2+1+1+2+1+3: unit/collaboration; `poetry` ✱ to unit/persistence | `tests/unit/collaboration/collaboration_data.py`; fixtures of `test_collaboration_workflow` (`ada`, `bob`, `books`, `now`, `plain`, `session`, `store`) → `tests/unit/collaboration/conftest.py`; `poetry` → `tests/toy.py` (a toy membership rule) |
| `unit/test_theme_layout` ✱ | 5: unit root, unit/{access,testkit} (+ module import, monkeypatched) | `tests/unit/layout_table.py` (new, unit root: `LAYOUT`, `PLACED`, `MOVED_MODULES`, `TURNED_ON`, `PACKAGE`, `ROOT`, `Placed`, `turned_on_*`); `test_no_old_module_paths.py:252` then patches the helper |
| `unit/test_technical_split` ✱ | 1: feature (`lint_scratch`) | `tests/unit/import_contracts.py` (feature already imports `Linted` from it; `LAYOUT` `:67`, `KEPT_CONTRACTS` `:91`, `SCRATCH_OVERRIDES` `:93` move with it) |
| `unit/testkit/test_shape_snapshot` ✱ | 1: generator/unit (`METAMODEL_PACKAGE`, `generated_models`) | `tests/metamodel.py` (new, root: crosses the two pyramids) |
| `generator/unit/test_generate_cli`, `test_freshness`, `test_freshness_plugin` | 5 + 4 + 2: generator/unit | `tests/generator/unit/golden.py` |
| `generator/unit/test_lock` | 2: generator/unit | `tests/generator/unit/lock_helpers.py` (new) |
| `generator/unit/test_hard_check`, `test_boundary_check` | 1 + 1: generator/unit (both export `problems_of`) | `tests/generator/unit/checks.py` (new; `hard_check_problems`, `boundary_problems`) |
| `generator/e2e/test_generated_library_served` | 1: generator/e2e (`PACKAGE`, `generated_toy` contextmanager) | `tests/generator/e2e/generated_toy.py` (new) |
| `integration/store/test_session` | 1: integration/store | `tests/integration/store/sessions.py` |
| `e2e/test_library` | 1: e2e | `tests/e2e/world.py` |

New root helpers: `tenancy_world.py`, `dump_helpers.py`, `relay_helpers.py`, `events_follow.py`,
`migration_helpers.py` (moved), `metamodel.py`. `tests/changed.py:59-70`: a `tests/<x>.py` file is
shared infrastructure (falls back to `make test-fast`); a `tests/unit/<x>.py` helper maps to no
rule (`:117-118`, also falls back). Both acceptable.

## 2. PD-11 moves

### Files directly in `tests/unit/` (30 tests + 5 non-tests)

**tooling → `tests/unit/tooling/` (13):** `test_adopt_validators` (manual's example), `test_changed`,
`test_check_docs`, `test_container_selection` (generator pyramid stamped by folder; not the
`testkit/` one of the same name), `test_docs_reference`, `test_import_contracts` (the scratch
import-linter helper), `test_lanes`, `test_library_tests_stay_apart`, `test_markers`,
`test_no_polling_hook`, `test_old_paths_gone`, `test_pre_commit_config`, `test_refresh_map`.

**package → `tests/unit/package/` (17):** `test_combined_artefacts`, `test_deprecated_paths_removed`,
`test_lazy_exports`, `test_log_calls`, `test_no_model_copy_update`, `test_no_old_module_paths`,
`test_packaging`, `test_public_api`, `test_public_surface`, `test_removed_keywords_adversarial`,
`test_smoke`, `test_sparql_parser_threads`, `test_technical_split`, `test_theme_contracts`,
`test_theme_domain_targets`, `test_theme_layout`, `test_theme_packages`.

**helpers:** `__init__.py`, `conftest.py` (stay; `GENERATED` `:19` to `tests/toy.py` per PD-11),
`builders.py` (stays: core, api, tenancy use it), `import_contracts.py` (stays at unit root: users in
tooling, package and feature; `:20` `parents[2]` unchanged), `sparql_threads.py` → `tests/unit/package/`
with its only runner (`test_sparql_parser_threads.py:22` `-m tests.unit.sparql_threads`, docstring `:4`).
New: `tests/unit/tooling/__init__.py`, `tests/unit/package/__init__.py`.

**`test_private_transaction_pieces.py`:** now `tests/unit/collaboration/` (an AST check of
`rdf_persistence/collaboration` source, `:14` `parents[3]`). With themes, `changed.py` maps
`rdf_persistence/collaboration/**` → `tests/unit/collaboration/`, so it reruns when its source
changes; moving it to tooling loses that. **Recommend: leave it; drop it from PD-11.**

### What names these paths (change on the move)

- **Self-located roots:** `ROOT/REPO = Path(__file__)...parents[2]` becomes `parents[3]` in 21 files:
  `test_combined_artefacts:13`, `test_library_tests_stay_apart:17`, `test_old_paths_gone:14`,
  `test_no_polling_hook:12`, `test_theme_domain_targets:14`, `test_theme_layout:17`,
  `test_lazy_exports:9`, `test_packaging:15`, `test_adopt_validators:16`, `test_log_calls:8`,
  `test_changed:22`, `test_sparql_parser_threads:15`, `test_no_model_copy_update:6`,
  `test_no_old_module_paths:20`, `test_technical_split:22` (and `:281`), `test_docs_reference:9`,
  `test_check_docs:10`, `test_public_surface:24`, `test_smoke:16`, `test_theme_contracts:22`,
  `test_theme_packages:12`.
- **Makefile:** `:55` comment names `tests/unit/test_lanes.py`; `:121` `refresh-snapshot` runs
  `tests/unit/test_public_surface.py`. No lane glob names a root file (`UNIT_LANE`/`LIBRARY_LANE`
  `:50-53` use `--ignore` of folders).
- **`tests/changed.py`:** `:73-75` `root_unit_tests()` globs `tests/unit/test_*.py` (empty after the
  move); rule 11 `:94-95` sends any non-theme `rdf_persistence/<x>` (e.g. `__init__.py`) to
  `root_tests`: change to `["tests/unit/package/"]` (folder, so it runs in parallel); `:105-106` rule 2
  `docs/**` → `tests/unit/test_check_docs.py` → `tests/unit/tooling/test_check_docs.py`. Rule 7/8
  `:80-86`: `tests/unit/tooling/x.py` and `package/x.py` then select their folder (len > 3), so the
  "root-level file runs alone" branch `:84-86` only serves unit-root test files (none left).
- **`tests/unit/test_changed.py`:** `:24` `ROOT_TESTS` fake pair; `:32` (rule 2 expects
  `test_check_docs` path); `:33` (rule 7 `tests/unit/test_public_api.py`); `:41` (rule 11 →
  `ROOT_TESTS`); `:206-211` (outside a theme selects the root tests); `:238-244`
  `test_the_root_level_unit_test_files_are_the_real_ones` asserts `tests/unit/test_changed.py` is
  listed (fails after the move: rewrite or drop with `root_unit_tests`); `:275`, `:296-305`,
  `:326-331`, `:431` use `tests/unit/test_public_api.py`/`test_markers.py` as example selections
  (strings only; fine to keep but misleading).
- **Spec:** `openspec/specs/rp-developer-checks/spec.md:118-121` ("select the root-level unit tests
  only"; "a selection of test files alone SHALL run on one process") and scenarios `:134-137`, `:144-147`
  (`tests/unit/test_public_api.py` runs alone): a MODIFIED delta is needed if rule 11 selects
  `tests/unit/package/`.
- **import-linter / setup.cfg / pytest.ini / CI:** none name a root test. `.importlinter:215-236`
  lists theme files only; `setup.cfg:25-29` mutation selection is theme folders + `test_tenant_move`;
  `pytest.ini:4` `testpaths = tests`; `.github/workflows/*.yaml`: no `tests/unit` path.
  Markers: `tests/conftest.py:85-93` row `unit/` is a prefix, covers the new subfolders.
- **Tests that name their own or a sibling's path:** `test_no_old_module_paths.py:36` `THIS_FILE`,
  `:46-53` allow-list (`tests/unit/test_theme_layout.py`, `test_technical_split.py`,
  `test_deprecated_paths_removed.py`), `:17`/`:252` module import of `test_theme_layout`;
  `test_public_surface.py:22`, `test_theme_contracts.py:20`, `access/test_wire_models.py:12`,
  `testkit/test_model_guard.py:9` import `tests.unit.test_theme_layout` (PD-8 moves these to
  `layout_table.py` first); `test_pre_commit_config.py:62` (`tests/unit/test_lanes.py` as a
  non-matching example: harmless); `test_library_tests_stay_apart.py:204` (`tests/unit/test_other.py`
  planted in tmp: harmless).
- **Data:** `tests/audit/scenario-map.csv`: 269 rows name a root file (counts per file: `test_changed`
  29, `test_lanes` 28, `test_theme_layout` 24, `test_refresh_map` 21, `test_technical_split` 21,
  `test_theme_contracts` 19, `test_check_docs` 17, ...): `make refresh-map` follows git renames
  against `BASE` (Makefile `:44-45`), so commit the `git mv` first. `.test_durations`: 693 keys with
  root paths (pytest-split averages unknown ones; run `make test-durations` after).
- **Docs:** `docs/modules/ROOT/pages/develop/testing.adoc:27` names
  `tests/unit/test_library_tests_stay_apart.py`.

## 3. `test_tenant_move.py`

- **Where:** `tests/unit/tenancy/test_tenant_move.py`. The module it tests moved too:
  `rdf_persistence/tenancy/services/tenant_move.py` (commit 3d96c742), not a domain module. It imports
  `core.domain.exceptions`, `iris.domain.layout`, `iris.services.generated.rp_iris_services.IriPolicy`,
  `iris.services.iris.Iris` (`tenant_move.py:13-16`).
- **Its imports today** (`test_tenant_move.py:7-20`): `core.domain.exceptions.InvalidBody`,
  `iris.domain.layout.stamps_graph_iri`, `iris.services.generated.rp_iris_services`
  (`IdKind`, `IdSpec`, `IriPolicy`, `ServiceSettings`), `iris.services.iris.Iris`,
  `schema.services.vocabulary as v` (used `:273`, `:303`, `:306`, `:330`: `DATA_SCHEMA_VERSION`,
  `ENTITY`, `vocabulary.py:113`, `:154`), `schema.services.schema.load_schema`,
  `schema.services.schema_structure.iri_types` (`:44-45` `iris_of`), `tenancy.services.tenant_move`,
  `tests.toy.SETTINGS, TOY_SCHEMA` (`SETTINGS` = `tests/toy.py:187-193`; 32 uses of
  `SETTINGS`/`iris_of`/`policy_settings`).
- **The removable ones:** `schema.services.*` (x3) and `tests.toy`: literal `URIRef`s for the two
  terms, literal `frozenset`s for `Iris(settings, roots, owned)` (`iris/services/iris.py:210-216`;
  defaults are empty frozensets), a local `ServiceSettings(...)` copy of the five fields. What stays
  is unavoidable: `iris.services` (Iris, the generated settings) and the module under test.
- **Contracts:** declared in `.importlinter` (root packages incl. `tests`, `:16-21`); the domain-test
  contract is `[importlinter:contract:domain-tests-stay-in-the-domain]` `:215-236`, `type = forbidden`,
  `allow_indirect_imports = True`, sources `tests.unit.core.*` x6, `tests.unit.iris.test_layout`,
  `tests.unit.files.test_blob_keys`, forbidden `rdf_persistence.*.services`, `*.adapters`,
  `*.entrypoints`, `rdf_persistence.testkit`, `tests.toy`, `tests.toy_service`. import-linter 2.11
  (`uv.lock:1101-1102`). `tests/unit/test_import_contracts.py:55` and `test_theme_contracts.py:36-45`
  read contracts by key (no count of contracts is asserted).
- **It cannot join that contract as is:** `rdf_persistence.*.services` forbids
  `tenancy.services.tenant_move` and `iris.services` themselves.
- **Minimal way (recommended):** keep the file where it is (`setup.cfg:29` mutation selection then
  stays valid; a subfolder would need `__init__.py` and a `setup.cfg` edit for nothing) and add its
  own contract after `:236`:

  ```ini
  [importlinter:contract:tenant-move-test-imports-only-its-module]
  name = the tenant-move test imports the module, the iris policy and the domain, nothing else
  type = forbidden
  allow_indirect_imports = True
  source_modules =
      tests.unit.tenancy.test_tenant_move
  forbidden_modules =
      rdf_persistence.schema
      rdf_persistence.*.adapters
      rdf_persistence.*.entrypoints
      rdf_persistence.testkit
      tests.toy
      tests.toy_service
  ```

  Alternative: add it as a source of `domain-tests-stay-in-the-domain` with three `ignore_imports`
  (`tests.unit.tenancy.test_tenant_move -> rdf_persistence.tenancy.services.tenant_move`, `->
  rdf_persistence.iris.services.iris`, `-> rdf_persistence.iris.services.generated.rp_iris_services`);
  more lines, and it blurs that contract's name. Old PD-11's "drop the `setup.cfg` line" no longer
  applies (`tenant_move.py` is still mutated, `setup.cfg:22`).

## 4. The guard

- **No existing guard** covers cross-test imports (grep of `tests/unit` and `tests/generator/unit`
  for cross-test/`test_` import checks: none). Closest precedent: `test_library_tests_stay_apart.py`,
  an AST scan of `tests/**/*.py` (`:80`) for generator imports; reuse its shape and its tmp-tree
  planting (`:148-207`).
- **`inputs/probes/cross_imports.py` is not enough as the template:** (1) scans only `test_*.py`
  (misses `sparql_threads.py`; the guard must scan every `tests/**/*.py`, conftests and helpers
  included); (2) checks only the module of an `ImportFrom`, so it misses `from tests.x import test_y`
  (4 today, above) and `from . import test_y`; (3) ignores `ast.Import` (`import tests.x.test_y`: none
  today); (4) resolves paths relative to the cwd (`pathlib.Path("tests")`): anchor on
  `Path(__file__).parents[3]` once in `tests/unit/tooling/`. Its relative-import resolution
  (`level`) is right and worth keeping. The planted test should cover all five forms: absolute
  `from`, relative `from .test_x`, `from pkg import test_x`, `from . import test_x`,
  `import tests.….test_x`.
- An import-linter contract is not a good fit: there is no wildcard for "any `test_*` module"
  across depths that is also excluded from the sources; the AST test is simpler.
