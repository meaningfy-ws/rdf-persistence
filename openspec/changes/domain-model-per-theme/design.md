# PLAN (design): domain-model-per-theme

Derives from the EPIC `domain-model-per-theme` (`proposal.md`, DEC-1 to DEC-8). Built after
`target-kind-from-the-model` is merged; its `derived_kind` (on `own_schemas`) is unchanged here: every
module in `rdf_persistence/model/` is non-technical, so each theme target derives `domain` either way.

## Context

On `develop` (df5a772): one domain target, `rdf_persistence/model/rp.yaml` →
`rdf_persistence.core.domain.generated`, with `version: "2"`, `migrations` and `diagrams`. The nine
modules of `rdf_persistence/model/` carry `python_package: rdf_persistence.core.domain.generated`.
In `rdf_persistence_generation/extensions/pydantic_split.py`: `generate_module_import` (183-196)
returns the local module for a schema beside the root, before the metamodel branch (consumer runs:
`public_package()`) and the `python_package` branch; `render` (357-370) builds one
`SplitPydanticGenerator` per schema of `own_schemas(view, folder)` from that schema's own path
(`_generator`, 341), `SplitMode.FULL` for the root (it imports every class of the closure) and
`AUTO` for the others, and names each file from `generate_module_import`. `python_package_problems`
(`checks/python_package.py`) checks `own_schemas` against `run.target.package`;
`stored_schema_problems` (`checks/hard.py:380-400`) fails a target without `migrations` whose
`root_classes(view, folder)` is not empty; `root_classes` also feeds `lock.py`, the frames
(`jsonld_context.py:155`) and `mermaid.py:47`. `rp.py` is imported only by
`tests/unit/core/test_rp_model.py:7`. `rdf_persistence/__init__.py` imports the domain modules
eagerly (44-109). 38 library modules and 81 test files deep-import them. `rp_tenancy` imports
`rp_access`; `access` uses `TenantAccess`/`TenantState`; `schema_structure.py:37` imports `StoredFile`,
`vocabulary.py:18` `TenantState`. `access/`, `provenance/`, `collaboration/` have no `domain/` package.
`tests/unit/test_theme_contracts.py:113` plants `files` → `provenance` as a failing import.

## Goals / Non-Goals

Goals: DEC-1 to DEC-6. Non-goals: the EPIC's no-gos.

## Decisions

Declared in the EPIC; planning decisions:

- **PD-1 Two sets of modules.** `generated_schemas(view, folder)` in `schema_structure.py`: the schemas
  of `own_schemas(view, folder)` whose `python_package` is absent or equals the root schema's. It feeds
  `render` (the Python files) and `python_package_problems`. `own_schemas` and `root_classes` keep
  feeding the shapes, the context, the frames, the lock and the mermaid diagrams.
- **PD-2 Import beside the root.** `SplitPydanticGenerator` gains `root_package: str | None`, set by
  `render`/`_generator` from the root schema's `python_package` annotation (the reference everywhere
  in this change; on the toolkit's run the hard check already makes it equal the entry's `package`).
  In `generate_module_import`, inside the "beside the root" branch only: when `root_package` is set
  and the module's `python_package` is set and differs, return `target_module(schema)`. The metamodel
  branch is unchanged, so a consumer's metamodel import goes through `rdf_persistence`.
- **PD-3 The package check.** `python_package_problems(view, folder, package, toolkit_packages)`:
  `steps.py` passes the packages of every toolkit `[[tool.rp-generate]]` entry (read with
  `read_targets` from the toolkit's `pyproject.toml`; empty on a consumer's run). For a schema of
  `own_schemas` outside `generated_schemas` on the toolkit's run: its `python_package` must be one of
  `toolkit_packages`, else `HardRule.PYTHON_PACKAGE_MISMATCH` with
  `"<module> names python_package <Q>, which no toolkit target generates"`. The existing rules run on
  `generated_schemas`.
- **PD-4 The migrations stay combined.** On the toolkit's run, `stored_schema_problems` runs only for
  the target whose root is `rdf_persistence/model/rp.yaml`; its closure holds every domain module, so
  every root (`TenantAccess`, `Comment` included) is checked there, and its lock is the one lock. The
  theme targets declare no `migrations` and write no lock. `root_classes` is unchanged. A consumer's
  run is unchanged.
- **PD-5 Root modules.** On the toolkit's run, a root schema with no classes of its own writes no
  module (`rp.py` goes); a root with classes of its own (`rp_tenancy.yaml`, `rp_files.yaml`,
  `rp_provenance.yaml`) is written in `SplitMode.AUTO`, so it imports only what it uses and re-exports
  no class of another theme. A consumer's root stays `FULL`. `test_rp_model.py` collects the classes of
  the five domain packages.
- **PD-6 The targets and the new root.** `rdf_persistence/model/rp_collaboration.yaml`: `id`
  `https://meaningfy.ws/ns/rdf-persistence/collaboration` (the pattern of `rp_access.yaml`'s
  `https://meaningfy.ws/ns/rdf-persistence/access`), `name:
  rp_collaboration`, `title: RDF persistence collaboration module` and a one-line `description`, the prefixes of `rp.yaml`, `imports: [linkml:types, rp_collections,
  rp_discussion, rp_workflow]`, annotation `python_package: rdf_persistence.collaboration.domain.generated`,
  no `module_kind`, no classes; `rp.yaml` does not import it. Annotations: `rp_access`, `rp_tenancy` →
  `rdf_persistence.access.domain.generated`; `rp_provenance` → `…provenance.domain.generated`;
  `rp_files` → `…files.domain.generated`; `rp_collections`, `rp_discussion`, `rp_workflow` →
  `…collaboration.domain.generated`. Four entries after the `rp.yaml` entry in `pyproject.toml`, each
  `schema`, `package`, `regenerate-command = "make generate"`, `openapi = false`, nothing else:
  `rp_tenancy.yaml` → `rdf_persistence.access.domain.generated`; `rp_provenance.yaml`,
  `rp_files.yaml`, `rp_collaboration.yaml` → their theme. Hand-written `domain/__init__.py` (a
  docstring) in `access`, `provenance`, `collaboration`.
- **PD-7 One commit for the move.** The annotations, `rp_collaboration.yaml`, the entries, the
  `domain/__init__.py` files, `make generate`, the eager domain imports of `rdf_persistence/__init__.py`
  (44-109), every deep import (38 library modules, 81 test files; ast-grep), the guards (PD-9),
  `themes-ordered` and the planted test at `test_theme_contracts.py:113` (`files-to-provenance`
  becomes `provenance-to-files`) land together; `import rdf_persistence` never fails between commits.
- **PD-8 Schema without upper imports** (DEC-6). `schema_structure.py` names the stored-file class
  from the schema (the class whose `class_uri` is `rp:StoredFile`, read from the SchemaView);
  `vocabulary.py` reads the tenant-state IRIs from the `TenantState` enum's `meaning`s in the
  SchemaView. Lands first (task 1.1).
- **PD-9 The guards.** `tests/unit/test_theme_layout.py` gains `MovedModule(theme, module)` rows,
  `old = rdf_persistence.core.domain.generated.<module>`, `new =
  rdf_persistence.<theme>.domain.generated.<module>`, one per moved module (seven), turned on
  together; `Move("<theme>", "domain", "generated", created=True)` for `access`, `provenance`,
  `collaboration`. `MovedModule` rows have no on switch; they stand at `new` from task 2.1.
  `turned_on_pairs()` also yields each `MovedModule`'s `(old, new)`, so `test_public_surface.py`
  (TC-02) and `test_no_old_module_paths.py` (TC-07) both read them; `public-surface.json` keeps the
  old paths.

## Algorithm / approach (in the order it lands)

1. PD-8, test first (task 1.1).
2. PD-1 to PD-5 in the generator, test first on fixtures (task 1.2); the `access` target proved end to
   end in a scratch copy (RISK-3).
3. PD-6, PD-7, PD-9 in one commit (task 2.1); TC-03, TC-04 compare with `v0.6.0`.
4. Docs and CHANGELOG (task 3.1).

### Anti-patterns

| Don't | Do | Why |
|---|---|---|
| swap `own_schemas` for `generated_schemas` everywhere | only in `render` and `python_package_problems` (PD-1) | `core` would lose frames, shapes and lock entries |
| write a re-export root module in `core` | no root module when the root has no classes (PD-5) | it imports every theme, breaking `themes-ordered` |
| read the reference package from the entry in one check and the annotation in another | the root's `python_package` everywhere (PD-2) | the two can disagree on a consumer's run |
| point a consumer or the kit at a theme target's partial `shapes.ttl` | load only `core/domain/generated/` (DEC-2) | the partial ones miss other themes' shapes |
| move YAML files, or hand-edit a generated file to pass TC-03 | regenerate; name a real difference in a D-n | LinkML is the single source |
| a re-export shim at the old module paths | the CHANGELOG lists the moved paths (DEC-8) | no deprecation release is planned |

## Error matrix

| ID | Input | Expected |
|---|---|---|
| E-1 | toolkit root with `python_package` P, beside a module with `python_package` Q ≠ P | Q's classes imported from Q; no file for that module in P |
| E-2 | toolkit module beside the root naming Q, which no toolkit entry has | `PYTHON_PACKAGE_MISMATCH`: "<module> names python_package <Q>, which no toolkit target generates" |
| E-3 | consumer schema importing `rdf_persistence/model/rp_access` | its generated code imports from `rdf_persistence` |
| E-4 | consumer root without `python_package`, beside a module with one | that module generated into the consumer's target |
| E-5 | consumer root with `python_package` P, beside a module with Q ≠ P | Q's classes imported from Q (PD-2), no package check (consumer's run); allowed |
| E-6 | the `access` target, which generates `TenantAccess` (a root), no `migrations` | passes; checked on `rp.yaml` (PD-4) |
| E-7 | the `collaboration` target, which generates `Comment` (a root), no `migrations` | passes; checked on `rp.yaml` |
| E-8 | `files.domain` importing `provenance.domain` | passes `themes-ordered` |
| E-9 | `provenance.domain` importing `files.domain`; `schema` importing `files` or `access` | fails `themes-ordered`, naming both |

## Test cases

| ID | Input | Expected | Where |
|---|---|---|---|
| TC-01 | `LAYOUT`, `MovedModule` rows | each moved module in its theme's `domain/generated/`; `core/domain/generated/` holds only `rp_core`, `rp_annotations` and the combined artefacts | `tests/unit/test_theme_layout.py` |
| TC-02 | the public surface | 148 names, each the same object; only its home module changes | `tests/unit/test_public_surface.py` |
| TC-03 | `core/domain/generated/{shapes.ttl,context.jsonld,*.frame.jsonld}`, `model/migrations/schema.lock.json` | equal to their `v0.6.0` copies, or each difference named in a D-n | task 2.1, before `make generate`: `git show v0.6.0:<path>` of the four artefact kinds copied into `tests/fixtures/v0_6_0/` (committed); `tests/unit/test_combined_artefacts.py` compares the regenerated files byte for byte; no git call at test time |
| TC-04 | `/openapi.json`, toy TypeScript, the model diagrams | unchanged | the existing golden tests |
| TC-05 | E-8, E-9 | as stated | `tests/unit/test_theme_contracts.py` (113 becomes `provenance-to-files`) |
| TC-06 | E-1 to E-7 | as stated | `tests/generator/unit/test_ext_pydantic_split.py` (E-1, E-3 to E-5), `test_python_package_rule.py` (E-2), `test_hard_check.py` (E-6, E-7); fixture `tests/fixtures/cross_target_beside/` (a root with `python_package` beside a module of another) |
| TC-07 | a moved module's old deep path | `ModuleNotFoundError` (a probe in `tests/unit/test_theme_layout.py`); no file names it (`test_no_old_module_paths.py`, from the `MovedModule` rows) | |
| TC-08 | `make test-containers` | passes | |

## Risks / Trade-offs

- **RISK-1 Consumers' deep imports break** (MWBv2). Likelihood medium, impact low. Mitigation: the
  CHANGELOG lists every moved path; MWBv2's upgrade is a change in its repo.
- **RISK-2 The combined artefacts or the lock change** when most modules are imported. Likelihood
  medium, impact medium. Mitigation: TC-03; PD-1 keeps them on `own_schemas`.
- **RISK-3 A cross-target edge the generator does not handle** (an enum or mixin of `rp_core` used by
  `rp_access`). Likelihood medium. Mitigation: task 1.2 proves the `access` target end to end first.
- **RISK-4 The one-commit move is large** (about 120 files). A broken intermediate state is excluded
  by PD-7; review cost high. Mitigation: ast-grep for the rewrites; the review reads the generator and
  the guards in full, the rewrites by sample.

## Open Questions

None.

## Accepted gate

- **DEC-9** (developer, 2026-11-19, "yes accept both"): the PLAN proceeds below 9/10 (run 2: 8.9),
  with every gap run 2 listed fixed as the gate stated it (`evidence/clarity-gate.md`).
