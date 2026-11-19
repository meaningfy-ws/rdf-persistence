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

## Delivery decisions

The lead's, shown for validation at the end (R-0007).

- **D-1 PD-5 applies only to a theme root** (task 1.2). PD-5 as written reaches every toolkit root;
  applied so, it stripped the re-exports of seven technical targets (`rp_access_services.py` and
  others) and deleted `rp.py` before the move. PD-5 now reads: on the toolkit's run, a root that
  shares its folder with modules naming another `python_package` writes no module without classes
  of its own, and is written in `SplitMode.AUTO` with some; every other root keeps its mode. `rp.py`
  goes in task 2.1, when `rp.yaml` first shares its folder with the other themes' modules.
- **D-2 Two package-mismatch tests point at the root** (task 1.2). With PD-3 a module naming a
  package no toolkit target generates gets E-2's message, which names no target package; the two
  tests that asserted "naming both" (`test_hard_check.py`, `test_python_package_rule.py`) now edit
  the root `rp`, where the old message still applies.
- **D-3 GitNexus rebuilt clean** (Prepare). The incremental re-index failed on a duplicate embedding
  key; per `develop/agents.adoc#reindex` the lead ran `clean --force` and a forced analyze, and
  checked task 1.1's impact by reading the code meanwhile (two constants, low). The incremental
  re-index before task 2.1 failed the same way; rebuilt clean again. An external tool's defect
  (GitNexus incremental embeddings), no workaround in the code.
- **D-4 Task 2.1's impact is HIGH, as planned.** `rp_tenancy.py` 15 direct / 44 total,
  `rp_access.py` 18 / 48: the move the PLAN sized (RISK-4, PD-7) and the developer decided at
  shaping (DEC-1 to DEC-5); not re-asked.
- **D-5 PD-4 skips only a theme target** (tester, after task 1.2; Critical, accepted). The
  stored-schema rules were skipped for every toolkit target but `rp.yaml`'s, so a new toolkit
  target with roots and no `migrations` would pass where it failed before: a hard check silently
  lost. Fix: on the toolkit's run, skip the rules only for a target whose root classes are all
  checked on `rp.yaml`'s target (the roots of `rp.yaml`'s closure); any other target keeps them.
  The tester's failing test is kept.
- **D-6 The conformance testkit reads every package a target's modules name** (task 2.1). With the
  metamodel over five packages, `Conformance.of(rp.yaml)` saw only `core`'s classes and seven
  conformance and round-trip tests failed (`KeyError: 'Grant'`). `_models_of` in
  `rdf_persistence_generation/testkit/conformance.py` adds the classes of each `python_package` of
  `own_schemas`. The testkit is in this repository, so this is the move's own fix, not a workaround.
  The theme targets also write a partial `shapes.ttl`, `context.jsonld` and frames beside their
  modules; as DEC-2 and the anti-patterns say, nothing loads them: the combined ones stay in `core`
  (TC-03 byte-identical to `v0.6.0`).
- **D-7 The review set** (developer, the session's brief, 2026-11-19: "one L2+L3 review pass plus
  the full review (L1, L2, L3 apart, L4+L5) as the epic's end"). The stage gets one pass of L2 and
  L3 together (P-0005's stage pass, applied here to a MEDIUM change by the developer's word, which
  overrides `develop/agents.adoc#challenge`'s "never combined" for this pass only); the epic's end
  gets the full review with L1, L2 and L3 apart and L4+L5 as one pass. The one stage is the epic's
  end, so both run on the same PR, in parallel.
- **D-8 The main spec's package scenario is modified** (review L2 W1; re-labelled Critical: the
  archive would write a requirement the code no longer meets into `openspec/specs/`). The
  requirement "The metamodel declares where its generated classes are imported from"
  (`openspec/specs/rp-generation/spec.md`) gets a MODIFIED delta: the reference is the root's
  `python_package`; the disagreeing scenario edits the root; a module generated by another target
  gets E-2's message.
- **D-9 E-2's spec delta states PD-3's rule** (review L2 W2, L2+L3 W1, L1 W2; re-labelled Critical:
  a spec delta untrue of the code). PD-3 decided "one of `toolkit_packages`"; the delta said "a
  toolkit target that generates it". The delta is reworded to PD-3. The stronger check (the target
  with that package has the module in its closure) is a follow-up, not this change.
- **D-10 The stored-schema skip needs no `migrations`** (review L1 W1, L2+L3 W4; re-labelled
  Critical, as D-5: a hard check silently lost). `_stores_its_roots_here` also skipped the version
  rule for a target that sets `migrations`; a theme target given `migrations` would write a second
  lock over `rp.yaml`'s. The rules are skipped only when the target sets no `migrations` and its
  roots are all `rp.yaml`'s; a test sets `migrations` on a theme target.
- **D-11 The pages say what ships** (review L2 W3–W5, L2+L3 W2–W3, L2 S10; re-labelled Critical:
  task 3.1's pages state the opposite of the code released as 0.7.0). `generation.adoc:300`, `:376`,
  `:381-384` (the false `rp.yaml` example), `:239-246` (the E-2 message), `develop/index.adoc:27,29`
  and `architecture/index.adoc:501` (`rp_collaboration.yaml`, the five domain packages); the
  CHANGELOG adds that a stored file is recognised by `class_uri rp:StoredFile`, not by name.
- **Under the floor** (the full review and the stage pass; follow-up issue): the E-2 closure check
  (D-9); `is_stored_file` scans every class per call (L4+L5 W2, L1 S2, L3 S3); `_metamodel_root_names`
  re-reads `pyproject.toml` and `rp.yaml` per target, `--project` ignored, no `is_file()` guard
  (L4+L5 W1, S1, L3 W1, L1 S3); the theme target is guessed three ways, not declared on
  `GenerationTarget` (L3 W2); the partial shapes, context and frames are written and shipped (L3 W3,
  L4+L5 S4, L2+L3 S5); `enum_meanings` and `TENANT_STATE_IRIS` kept in `schema` for tests only,
  stale `vocabulary` docstring (L3 W4, L4+L5 W4, S3); `TOOLKIT_ROOTS` patched in eleven modules
  (L3 W5, L2+L3 S3; a test pattern of this repository, not a library workaround); `_generated_here`
  and `generated_schemas` duplicate one predicate, three readers of `python_package`, generator-only
  helpers in the library (L4+L5 W3, L3 S1, L2+L3 W5, S1); `METAMODEL_ROOT` and `PYPROJECT` repeat
  other constants (L4+L5 S2, L3 S2, L2+L3 S2); asserts with `and` chains or no message, one duplicate
  test (L2 W6); the theme map written five times, test modules importing from test modules (L3 S4);
  the `v0.6.0` fixtures pinned for good (L3 S5) and compared by bytes, not graphs (L2 S8); the
  hand-written `schema` import check repeats `themes-ordered` (L3 S6); no check of each theme
  folder's modules (L2 S7, L2+L3 S4); a scenario-map note and row (L2 S7, S9).
- **Under the floor** (tester, after task 1.2):
  - `_toolkit_packages` raises `ConfigError` on a toolkit `pyproject.toml` without
    `[[tool.rp-generate]]` entries: the toolkit cannot have one (Warning).
  - `stored_file_class` sees only the first of two classes claiming `rp:StoredFile`: one claimant
    in every schema we ship (Suggestion).
  - `enum_meanings` turns a value without `meaning` into `URIRef('None')`: it reads only the
    metamodel's own `TenantState`, whose values all have one (Suggestion).
  - `enum_meanings` of an unknown name raises an unnamed `AttributeError`: callers pass a constant
    name (Suggestion).
