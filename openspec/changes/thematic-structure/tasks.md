> Derives from: EPIC `thematic-structure` (proposal.md). Eight stages, one PR each into `develop`.
> Type: Implementation (a staged move).

`PD-n` is a decision of [design.md](design.md). `LAYOUT` is the table of PD-1 held in
`tests/unit/test_theme_layout.py`. "The recipe" is design.md's six steps.

**How it succeeds:** after stage 7 every row of `LAYOUT` holds, the contracts of PD-6 pass, the 149
public names are the same objects, `/openapi.json` and the toy's generated output are unchanged
apart from the template line, and `git log --follow` reaches each moved file's history. **How it
fails:** a module, import or string on an old path (TC-01, TC-04), a theme importing upward
(`themes-ordered`), a misplaced model (PD-4), a changed artefact (TC-07). All are checked by
`make check-all`, `make check-generation` and `make test-containers` at each stage's end.

Every task is test first. Its gate is `make test-changed check-quality`; a task that moves `core`
or a port, or rewrites imports across themes, uses `make test-fast check-quality`. After the lead
commits a schema change: `make check-generated`.

## Stage 1: the generator and the guards (PR 1, old layout)

- [x] 1.1 Check ASM-1 to ASM-3 on `develop` (technical groups and paths, the `iris.py` split,
  `python_package`, the generator's package, logger names, and any module the earlier changes
  created that PD-1's map lacks) and amend design.md PD-1/PD-2/PD-3 where they differ, before any
  code. No test; the lead reviews the amendment. Done 2026-11-18 on 79c6837: ASM-1 to ASM-3 hold;
  design.md amended (D-1).
- [x] 1.2 PD-3: cross-target imports in `rdf_persistence_generation/extensions/pydantic_split.py`
  (the module→package map over every `python_package`). Tests in
  `tests/generator/unit/test_ext_pydantic_split.py` and a two-target fixture under
  `tests/fixtures/`. Gate: `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-10 | target B's schema imports module `a` of target A, which declares `python_package: pkg.a.generated` | B's code has `from pkg.a.generated.a import X`; no class `X` in B; B's manifest lists `a.yaml` |
| TC-11 | the same, `a` without `python_package` | as today: `a`'s classes are generated into B |
| TC-12 | a toolkit per-theme technical module whose `python_package` differs from its target's `package` | `generator-package` PD-6 (b)'s hard-check problem (`checks/python_package.py:29`), unchanged (no new check here); nothing written |

- [x] 1.3 PD-4: `kind_folder_problems` in `rdf_persistence_generation/checks/boundary.py`, wired
  into `steps.py`'s `_boundary_problems` (lines 96-101) for the toolkit's run; the model guard's
  per-theme scan in `tests/unit/testkit/test_model_guard.py` (moved there by `generator-package`;
  the generator's own call there stays, PD-4 (c)). Tests in `tests/generator/unit/test_boundary_check.py` and
  `tests/unit/testkit/test_guards.py`. Gate: `make test-changed check-quality`, then the lead's
  `make check-generated`.

| ID | Input | Expected |
|---|---|---|
| TC-13 | toolkit run, `kind = "domain"`, `package = "x.core.domain.generated"` | no problem |
| TC-14 | toolkit run, `kind = "technical"`, `package = "x.access.domain.generated"` | problem naming target and package |
| TC-15 | toolkit run, `kind = "domain"`, `package = "x.access.adapters.generated"` | problem |
| TC-16 | consumer run, `kind = "technical"`, `package = "app.generated"`; and a target without `kind` | no problem (as today) |
| TC-17 | a pydantic class in a fixture module `<pkg>/tenancy/services/x.py` outside `generated`, guard called with `layers=("tenancy",)` | the guard fails naming it; the same class under `<pkg>/tenancy/services/generated/` passes |
| TC-72 | `make generate` on the toolkit as `develop` has it (old layout: `rdf_persistence.services.generated.service`, `rdf_persistence.adapters.generated`, `rdf_persistence.testkit.generated`, `rdf_persistence_generation.generated`), then one target's `package` edited to `rdf_persistence.domain.generated.service` | first passes (the testkit and generator packages are exempt); second fails naming that target (the check is wired) |

- [x] 1.4 PD-8 template: a consumer run writes `from rdf_persistence import RpModel as ...`; the
  toolkit run writes the `core` path (in stage 1 still `rdf_persistence.domain.base`, read from the
  metamodel's `python_package` owner). `make generate` refreshes the toy library. Tests in
  `tests/generator/unit/test_templates.py` (new; it does not exist yet).

| ID | Input | Expected |
|---|---|---|
| TC-18 | the toy library generated | every module imports `RpModel` from `rdf_persistence`; it type-checks (`mypy-generated.ini`) |
| TC-19 | the toolkit's metamodel generated | it imports `RpModel` by its module path (`rdf_persistence.domain.base` now, the `core` path from stage 2), never from `rdf_persistence` |

- [x] 1.5 PD-10: components merged over the served targets; `SERVED_SCHEMAS`; the TypeScript step
  over all of them. While only `rp_service` is served, output is unchanged. Tests in
  `tests/unit/services/test_components_folder.py` (extended: it holds TC-54, the toolkit folder;
  the merge of several folders, TC-20 and TC-21, goes beside it, since `services/components.py`
  is what merges), `tests/generator/unit/test_openapi_components.py` (the generator side, if the
  step changes) and `tests/generator/unit/test_ext_typescript.py`.

| ID | Input | Expected |
|---|---|---|
| TC-20 | two component files, disjoint names | merged, in `SERVED_SCHEMAS` order |
| TC-21 | two component files declaring `Page` | error naming `Page` and both files |
| TC-07 | `/openapi.json` of the toy service, and the toy's TypeScript, before and after | byte-identical (golden files under `tests/fixtures/`, written by this task before any split) |

- [x] 1.6 The guards of the move: `tests/unit/test_theme_layout.py` (`LAYOUT`, every row off),
  `tests/unit/test_public_surface.py` (the 149 names snapshot: name → defining module and object
  identity through the lazy map; `tests/unit/test_public_api.py` stays as it is),
  `tests/unit/test_no_old_module_paths.py` (ast and text search for the old module paths of rows
  turned on; not `test_no_old_paths.py`, which would sit beside `generator-package`'s
  `tests/unit/test_old_paths_gone.py`, the scan for the generator's old path), and `tests/changed.py` learning themes (PD-11). Tests in
  `tests/unit/test_changed.py`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | a row of `LAYOUT` turned on whose module is still at its old path | fails naming old and new path |
| TC-03 | `rdf_persistence.__all__` and `getattr(rdf_persistence, n)` for each name | 149 names, each the object at its `LAYOUT` home |
| TC-04 | the string `rdf_persistence.services.session` in a test's `mock.patch` once its row is on | fails naming the file and line |
| TC-22 | `tests.changed` with `rdf_persistence/tenancy/services/sweep.py` changed | `tests/unit/tenancy/` |
| TC-23 | `tests.changed` with `rdf_persistence/core/domain/sparql.py` changed | exit 3 (`make test-fast`) |

Stage 1 closes with the lead's full gates, the review (L1 to L5), the fix pass, PR 1.

## Stage 2: `core` (PR 2)

- [x] 2.1 The recipe for `core` (PD-1 row; PD-2 `core/adapters`): `domain/{base,exceptions,media,sparql,sparql_parsing}`,
  `services/{artifacts,yaml_files,telemetry}`, `adapters/_http`, and the metamodel target
  `domain/generated/` → `core/domain/generated/` (every `python_package` and `public_package`
  annotation, the `[[tool.rp-generate]]` entry; the `python_import` annotation of
  `technical-models`' `SparqlTerm` type). The `domain.base` shim (PD-8). PD-4 (a), (b): the guard's
  `FORBIDDEN_BASES` and `DEFAULT_ALLOW` gain the `core` path. PD-2 `core/services` (`HttpSettings`,
  `LogContext`). `themes-layered` and `themes-ordered` created with `core`; `layers-across-themes`
  added; the old `layers` contract kept. The two `ignore_imports` lines of
  `sparql-parser-only-through-the-wrappers` that name `domain.sparql_parsing` move with it, and
  `domain-tests-stay-in-the-domain` gains the moved test modules as sources (PD-6).
  `tests/unit/domain/test_{rp_model,exceptions,sparql,sparql_parsing}.py` → `tests/unit/core/`. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `LAYOUT` rows of `core` | hold |
| TC-03 | the public surface | unchanged objects; `RpModel` defined in `rdf_persistence.core.domain.base` |
| TC-05 | `import rdf_persistence.domain.base`, in a fresh interpreter (a subprocess, since the warning fires on first import only) | one `DeprecationWarning` naming `rdf_persistence.core.domain.base`; `RpModel` is the same object; no module of `rdf_persistence/` imports it (grimp) |
| TC-06 | every `__init__.py` under `rdf_persistence/<theme>/` (ast) | holds a docstring and nothing else (PD-9) |
| TC-24 | a fixture consumer module `class Book(RpModel)` with `from rdf_persistence import RpModel` | `assert_models_generated` flags it (fails before PD-4 (a), since the export now resolves to `rdf_persistence.core.domain.base.RpModel`) |
| TC-08 | `make generate` after the move | metamodel output identical apart from its folder and the manifests; lock unchanged |
| TC-02 | `git log --follow --oneline rdf_persistence/core/domain/sparql.py` | reaches the commit that created `domain/sparql.py` |

## Stage 3: `iris`, `schema`, `files`, `provenance` (PR 3)

- [x] 3.1 PD-5: the recipe for `iris` (`domain/layout.py` → `iris/domain/layout.py`,
  `services/iris.py` → `iris/services/iris.py`, the halves `technical-models` split), then the 11
  wrappers removed, `mint_aggregate_iri` warning; their users rewritten to `DEFAULT_IRIS` or a
  policy `Iris` (the full list in PD-5, integration, perf and `tests/toy_service.py` included;
  `tenant_resource_name(prefix, t)` becomes `Iris.resource_name(t)` on an `Iris` whose settings
  carry that prefix) (`tests/unit/services/test_iris*.py`, `test_iri_policy*.py` and
  `tests/unit/domain/test_layout.py` → `tests/unit/iris/`). PD-2 `iris/services`. Gate:
  `make test-fast check-quality`; the lead runs `make test-containers` (integration users).

| ID | Input | Expected |
|---|---|---|
| TC-30 | `from rdf_persistence.iris.domain import layout` | the 12 functions; the module imports only `rdf_persistence.core.domain` |
| TC-31 | `rdf_persistence.iris.services.iris` | has none of the 11 removed names |
| TC-32 | `rdf_persistence.mint_aggregate_iri(t, "books")` | `DeprecationWarning` naming `Iris.mint_aggregate`; same IRI shape as `DEFAULT_IRIS.mint_aggregate(t, cls_type="", rp_path="books")` |
| TC-33 | the existing IRI and IRI policy tests, on `Iris` instances | pass unchanged in what they assert |

- [x] 3.2 The recipe for `schema`, `files`, `provenance`. `schema/services/schema.py`'s
  `PACKAGE_DIR` still resolves `rdf_persistence/` (it uses `resources.files`, not `__file__`);
  `metamodel_importmap()` unchanged. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `LAYOUT` rows of the four themes | hold |
| TC-34 | `metamodel_importmap()` | the same mapping as before the move |
| TC-35 | `make check-architecture` | `themes-ordered` holds `iris | schema` and `provenance | files` |

## Stage 4: `persistence` and `migrations`, the store split (PR 4)

- [x] 4.1 PD-7: `SparqlProtocolStore` and `FusekiStore`. If `second-store` is planned first, this
  task is its own PR in the old layout (`adapters/sparql_protocol.py`). Tests:
  `tests/unit/persistence/test_sparql_protocol_store.py` (a subclass over `httpx.MockTransport`),
  `test_fuseki_store.py` unchanged apart from imports and the `caplog` logger name (PD-7). Gate:
  `make test-changed check-quality`;
  the lead runs `make test-containers`.

| ID | Input | Expected |
|---|---|---|
| TC-40 | a minimal subclass with paths `/q`, `/u`, `/g`; `query`, `update`, `put_graph` | requests to those paths with today's headers and bodies |
| TC-41 | answers 400, 404, 409, 500, 401 to that subclass | `BadQuery`, `DatabaseGone`, `Conflict`, `StoreUnavailable`, `StoreUnavailable`; messages name its `service` |
| TC-42 | `SparqlProtocolStore` instantiated directly | `TypeError` (abstract) |
| TC-43 | the store conformance suite on Fuseki | passes unchanged |

- [x] 4.2 The recipe for `persistence` (with `fuseki.py`, the `adapters.fuseki` shim) and
  `migrations`. PD-2 `persistence/services`, `persistence/adapters`, `migrations/services`.
  `migrations-below-the-runner` removed (implied). Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `LAYOUT` rows | hold |
| TC-44 | `from rdf_persistence.adapters.fuseki import FusekiStore` | `DeprecationWarning`; same class as `rdf_persistence.FusekiStore` |
| TC-07 | `/openapi.json`, toy TypeScript | unchanged (now from two served targets) |
| TC-45 | `make check-architecture` with a planted `persistence.services → access.services` import | `themes-ordered` fails naming both |

## Stage 5: `access` and `tenancy` (PR 5)

- [x] 5.1 The recipe for `access` and `tenancy`, with `services/tenant_move.py` (moved out of
  `domain` by `technical-models`, DEC-3) → `tenancy/services/tenant_move.py`. PD-2 `access/services`, `access/adapters`,
  `tenancy/services`. `tenancy-without-the-runner` retargeted. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `LAYOUT` rows | hold |
| TC-50 | the `Zitadel*` records and `JwtClaims` | generated in `rdf_persistence.access.adapters.generated`; none under any `domain` |
| TC-51 | a planted import of `rdf_persistence.access.adapters.generated` from a module of `rdf_persistence.tenancy.services` | `layers-across-themes` fails |
| TC-07 | `/openapi.json`, toy TypeScript | unchanged |

## Stage 6: `events`, `collaboration`, `messaging` (PR 6)

- [x] 6.1 The recipe for the three themes. PD-2 `events/services`, `collaboration/services`.
  `collaboration-layers`, `session-and-provenance-without-mapper` and
  `event-bus-libraries-in-one-module` retargeted; `nothing-in-services-imports-the-bus` removed.
  Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `LAYOUT` rows | hold |
| TC-60 | a planted import of `rdf_persistence.messaging.services.messagebus` from `rdf_persistence.collaboration.services.workflows` | `themes-ordered` fails |
| TC-61 | a planted `import faststream` in `rdf_persistence.events.services.relay` | `event-bus-libraries-in-one-module` fails |

## Stage 7: `api`, the end of the old layers, the deprecation release (PR 7)

- [ ] 7.1 The recipe for `api` (`services/{aggregates,documents,file_removal,components,shacl}`, all of
  `entrypoints/`; `tests/unit/services/test_shacl.py` → `tests/unit/api/`; the `ignore_imports` line
  `services.shacl -> pyshacl` of `sparql-parser-only-through-the-wrappers` retargeted, PD-6). PD-2 `api/entrypoints`. `services/` and `entrypoints/` deleted;
  `domain/` and `adapters/` hold only the shims. The old `layers` contract removed; `.importlinter`
  is PD-6's final form, without `technical-models`' `domain-never-imports-technical-models`, with
  `api-services-never-import-the-bus` retargeted to `api.services` and its planted tests re-pointed (D-23). The
  emptied `model/technical/<group>/` schemas deleted (all but `testkit`'s). `ruff.toml` per-file
  ignores and `.coveragerc` on new paths. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | every row of `LAYOUT` | holds |
| TC-70 | `rdf_persistence/` top level | exactly the 13 themes, `domain` and `adapters` (shims), `model`, `testkit`, `__init__.py`, `py.typed` |
| TC-73 | `make generate` on the toolkit, then one target's `package` edited to `rdf_persistence.access.domain.generated` | first passes on the theme layout; second fails naming that target (PD-4, wired since task 1.3) |
| TC-03 | the public surface | 149 names, each the same object as before stage 2, except `mint_aggregate_iri` (a warning wrapper since stage 3) |
| TC-07 | `/openapi.json`, toy TypeScript | unchanged |
| TC-71 | the toy end-to-end test (`make test-containers`) | passes; `assert_public_imports` finds only top-level and testkit names |

- [ ] 7.2 Docs: `architecture/index.adoc` (the theme map and its order, the rule of DEC-3),
  `architecture/generation.adoc` (targets per theme, cross-target imports), every page naming a
  module path; `questions.adoc` gains "Where does a module live?"; CHANGELOG "Deprecated" (the two
  shims, `mint_aggregate_iri`, logger names). `make check-docs check-diagrams`.

Stage 7 closes with the lead's full gates, the review, PR 7, and a minor release (PD-13).

## Stage 8: remove the deprecated paths (PR 8, after the release of stage 7)

- [ ] 8.1 Check that a release containing stage 7 is published (PD-13); then delete
  `rdf_persistence/domain/`, `rdf_persistence/adapters/`, `mint_aggregate_iri` and its export
  (`__all__` becomes 148 names). CHANGELOG "Removed", **BREAKING**. Gate:
  `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-80 | `import rdf_persistence.domain.base` | `ModuleNotFoundError` |
| TC-81 | `rdf_persistence.mint_aggregate_iri` | `AttributeError` |
| TC-03 | the public surface | 148 names, the rest unchanged |

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5 · [x] 1.6 · [x] 2.1 · [x] 3.1 · [x] 3.2 ·
  [x] 4.1 · [x] 4.2 · [x] 5.1 · [x] 6.1 · [ ] 7.1 · [ ] 7.2 · [ ] 8.1

## Verification

Per stage: `make check-all`, `make check-generation`, `make test-containers` (lead), TC-01, TC-03,
TC-07 and TC-02; for the change: `make check-spec` and the clarity gate on this PLAN (≥ 9/10).
