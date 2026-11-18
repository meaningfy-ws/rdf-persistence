> Derives from: EPIC `generator-package` (proposal.md). Four stages, one PR each into `develop`.
> Type: Implementation.

`PD-n` is a decision of [design.md](design.md). "The generator" is `rdf_persistence_generation`
after stage 2 and `rdf_persistence.generation` before it. "The toy" is the toy library of
`tests/fixtures/library/`. Starts after `technical-models` and `otel-observability` have merged.

How the change succeeds: `make check-all`, `make check-generated` and `make test-containers` pass at
the end of each stage; `make check-generated` shows no diff outside the manifests' input paths
(stage 2) and none at all (stages 1, 3, 4). How it fails: an import contract, the packaging test, a
TC below or a generated diff. Every task is test first. Its gate is
`make test-changed check-quality`, or `make test-fast check-quality` where the task says so.

## Stage 1: the testkit stops importing the generator, but for configuration (PR 1)

- [x] 1.1 PD-1: on `develop`, the import cut's test: list every name a module of
  `rdf_persistence/testkit/` (other than `freshness.py` and `conformance.py`) imports from
  `rdf_persistence.generation`. `technical-models` task 4.1 moved every such record into
  `rdf_persistence.testkit.generated`, so the expected list is empty and the task is TC-01 to
  TC-04; a record added since is moved the same way (PD-1). Tests in a new
  `tests/unit/testkit/test_testkit_imports.py`. Gate: `make test-changed check-quality`, then
  `make check-generated`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `ast` scan of every module of `rdf_persistence/testkit/` except `freshness.py` and `conformance.py` (as `technical-models` TC-50 and the task 1.2 contract; `roundtrip.py` and `strategies.py` reach the generator only through `conformance`) | no import from `rdf_persistence.generation`; on failure the message names module and name |
| TC-02 | the generated `rp_generation` module; `rdf_persistence.testkit.generated` | none of the records a library testkit module imports is defined in the first; each is in the second |
| TC-03 | `rp_generation.yaml` | declares `ConstraintCase` and `ConstraintKind` (the conformance suite's, PD-1) and none of the records of `technical-models` PD-11 |
| TC-04 | `make check-generated` | no diff; the `testkit` target's `kind` check passes |

- [x] 1.2 DEC-3, first half: contract `testkit-imports-the-generator-only-for-configuration` in
  `.importlinter` (forbidden: source `rdf_persistence.testkit`, forbidden
  `rdf_persistence.generation`; `ignore_imports` the edges from `testkit.freshness` and
  `testkit.conformance`). Stage 2 replaces it. Gate: `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-05 | `make check-architecture` | the new contract is kept |
| TC-06 | (adversarial tester, reverted) `from rdf_persistence.generation.config import read_targets` added to `testkit/guards.py` | `make check-architecture` fails naming `guards` and `generation.config` |

Stage 1 closes with `make check-all`, `make test-containers`, the review (one pass, L1+L3), PR 1.

## Stage 2: the sibling package (PR 2)

- [x] 2.1 DEC-1, DEC-2, PD-7, PD-4, PD-5: the packaging test first, then the move (design,
  "Stage 2, step by step", 1, 2, 4 and 5). Tests in `tests/unit/test_packaging.py` and
  `tests/unit/generation/test_freshness.py`, `test_generation_inputs.py` (moved in 2.4). Gate:
  `make test-fast check-quality`, then `make check-generated` (the lead reads the diff).

| ID | Input | Expected |
|---|---|---|
| TC-07 | `uv build --wheel`, its file list | contains `rdf_persistence/py.typed`, `rdf_persistence_generation/py.typed`, `rdf_persistence_generation/model/rp_generation.yaml`, every file of `rdf_persistence_generation/templates/`, `rdf_persistence/model/rp_core.yaml`; no `rdf_persistence/generation/` |
| TC-08 | the wheel's `entry_points.txt` | `rp-generate = rdf_persistence_generation.cli:main` |
| TC-09 | `make generate` after the move | the diff is the `rp-manifest.json` files of every target (the toolkit's and the toy's), input paths only: `rdf_persistence/generation/...` → `rdf_persistence_generation/...` |
| TC-10 | `recorded_path` of a file in the library, in the generator, and in `base` | `rdf_persistence/...`, `rdf_persistence_generation/...`, the path relative to `base` |
| TC-11 | `is_toolkit_schema` with the generator's `TOOLKIT_ROOTS` for `rdf_persistence_generation/model`, `rdf_persistence/model`, the toy folder | true, true, false |
| TC-12 | the library's `is_toolkit_schema` with its default roots for `rdf_persistence_generation/model` | false (the library knows only itself) |
| TC-13 | `rp-generate --check` in an environment where `import linkml` fails (the existing test's monkeypatch) | compares the manifests; exit 0 on the fresh tree |
| TC-14 | `rp-generate` with no `generate` extra, not `--check` | exit 2, the message names `rdf-persistence[generate]` |
| TC-14a | ast-grep `is_toolkit_schema($$$A)`, `apply_defaults($$$A)`, `generation_view($$$A)` over `rdf_persistence_generation/` (PD-5) | every match passes `roots=`; a planted call without it (adversarial, reverted) fails naming file and line |
| TC-14b | `class_shapes([rp_generation.yaml], roots=TOOLKIT_ROOTS)` against `rdf_persistence_generation.generated` (`tests/generator/unit/test_generation_shape.py`) | `model_shape_diff` is empty |
| TC-14c | `grep -rn "rdf_persistence/generation\|rdf_persistence\.generation"` outside `openspec/` and `CHANGELOG.md`, at the close of the stage | nothing |

- [x] 2.2 PD-2, PD-3: the four modules to `rdf_persistence_generation/testkit/`, its lazy
  `__init__`, the shims; `tests/conftest.py:37` loads `rdf_persistence_generation.testkit.freshness`;
  `tests/unit/services/test_activity_shape.py` and `test_mapper.py` import the new paths. Tests in
  `tests/unit/generation/test_testkit_moved.py` (moved in 2.4), `tests/unit/test_testkit_lazy_import.py`
  and `tests/unit/testkit/test_stage1_adversarial.py` (both keep testing the four lazy names, now
  through the shims). Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-15 | `import rdf_persistence.testkit.conformance` in a fresh interpreter | one `DeprecationWarning` naming `rdf_persistence_generation.testkit.conformance`; `.Conformance is rdf_persistence_generation.testkit.conformance.Conformance` |
| TC-16 | same for `freshness`, `roundtrip`, `strategies` | the same, each naming its new module |
| TC-17 | `from rdf_persistence.testkit import Conformance, conformance_problems, round_trip, aggregate` | the moved objects, with the warning |
| TC-18 | pytester session with `pytest_plugins = ["rdf_persistence.testkit.freshness"]` and a stale toy copy | the session stops with the stale message and the regenerate command (old path works) |
| TC-19 | the same with `rdf_persistence_generation.testkit.freshness` | the same; no `DeprecationWarning` |
| TC-20 | `import rdf_persistence.testkit` | no `DeprecationWarning` (the shims load only on use) |
| TC-21 | `import rdf_persistence_generation.testkit` with `linkml` made unimportable | imports; `Conformance` loads |

- [x] 2.3 PD-8, DEC-3: `.importlinter` (root packages, `library-never-imports-the-generator`,
  `runtime-without-extras`, `works-without-the-generate-extra`); stage 1's contract removed. Gate:
  `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-22 | `make check-architecture` | every contract kept; the new contract's `ignore_imports` has exactly the four shim edges |
| TC-23 | (adversarial tester, reverted) `import rdf_persistence_generation.config` in `rdf_persistence/services/schema.py` | fails naming both modules |
| TC-24 | (adversarial tester, reverted) `import linkml` in `rdf_persistence_generation/manifest.py` | `works-without-the-generate-extra` fails |

- [x] 2.4 DEC-8, PD-9, PD-10: move the tests; `_MARKERS_BY_DIR`; `tests/changed.py`; Makefile
  lanes and path lists (with `refresh-snapshot`, `refresh-golden`, `ruff.toml:61`,
  `.pre-commit-config.yaml:24`); `sonar-project.properties`; CI job `test-generator`; the `ast`
  test of PD-9 with `TOOL_USERS`; the `generation` parameter of the shape test split out (PD-9). Tests in `tests/unit/test_container_selection.py` (marker rows), `tests/unit/test_changed.py`,
  `tests/unit/test_library_tests_stay_apart.py`. Gate: `make test-fast check-quality`, then
  `make test-unit test-feature test-generator`.

| ID | Input | Expected |
|---|---|---|
| TC-25 | items collected from `tests/generator/unit/x`, `feature/x`, `integration/x`, `e2e/x` | markers `unit`; `feature`; `integration` and no container marker; `e2e`, `store`, `files`, `identity` |
| TC-26 | `tests.changed` for `rdf_persistence_generation/manifest.py` | `tests/generator/` |
| TC-27 | a library test file with `import rdf_persistence_generation`, and one with `pytest_plugins = ["rdf_persistence_generation.testkit.freshness"]`, neither in `TOOL_USERS` (in `tmp_path`, fed to the checker) | the checker names each file |
| TC-28 | the repository's own tests | the checker finds nothing; every file it finds importing the generator is in `TOOL_USERS` (the eight of design PD-9) |
| TC-28a | `TOOL_USERS` with an extra entry whose file imports no generator module | the checker names the stale entry |
| TC-29 | `make test-unit` | collects nothing under `tests/generator/`; coverage over `rdf_persistence` ≥ 80 % |
| TC-30 | `make test-generator` | collects only `tests/generator/`; coverage over `rdf_persistence_generation` ≥ 80 % |
| TC-31 | test count before and after the move (`pytest --collect-only -q` over `tests/`) | equal, plus the new tests of stage 2 |

- [x] 2.5 Docs: `architecture/generation.adoc` (the package, the plugin path, the shims),
  `architecture/index.adoc:314` (the row), `howto/adopt.adoc` (§ freshness: the new
  `pytest_plugins` line; the conformance imports; "after upgrading, regenerate once"),
  `develop/index.adoc:90`, `develop/testing.adoc` (§ Where tests live: the two pyramids). Gate:
  `make check-docs`.

Stage 2 closes with `make check-all`, `make check-generated`, `make test-containers`, the review
(L1, L2, L3 apart; L4+L5 one pass), the fix pass, PR 2, and the shim-removal issue opened.

## Stage 3: the metamodel says where its classes live (PR 3)

- [ ] 3.1 DEC-7, PD-6: `python_package` and `public_package` in `GenerationAnnotation`; the
  annotations on `model/rp.yaml`, every `model/rp_*.yaml`, every technical group's schema and
  `rp_generation.yaml`; `metamodel_module` reads them (design PD-6); the
  constants deleted; the two hard-check rules. Tests in
  `tests/generator/unit/test_ext_pydantic_split.py` and `test_hard_check.py`. Gate:
  `make test-fast check-quality`, then `make check-generated` (no diff).

| ID | Input | Expected |
|---|---|---|
| TC-32 | `metamodel_module(<rp_core's SchemaDefinition>, toolkit=True)` | `rdf_persistence.domain.generated.rp_core` |
| TC-33 | `metamodel_module(<rp_core's SchemaDefinition>, toolkit=False)` | `rdf_persistence` (from `rp.yaml`'s `public_package`) |
| TC-34 | a metamodel copy whose `rp_core.yaml` says `python_package: rdf_persistence.kernel.generated` | toolkit import `rdf_persistence.kernel.generated.rp_core` |
| TC-35 | a metamodel copy with `rp_files.yaml` lacking `python_package`, toolkit run | hard-check problem naming `rp_files`; nothing written |
| TC-36 | `rp_core.yaml` says `python_package: x.generated`, the toolkit entry for `rp.yaml` says `rdf_persistence.domain.generated` | hard-check problem naming `rp_core`, `x.generated` and `rdf_persistence.domain.generated` |
| TC-37 | the toy's run (a consumer) with TC-36's metamodel | no problem from rule (b); imports from `rdf_persistence` |
| TC-38 | `python_package` of `model/technical/wire/rp_wire.yaml`, `model/technical/service/rp_service.yaml`, `model/technical/testkit/rp_testkit.yaml`, `rdf_persistence_generation/model/rp_generation.yaml` | `rdf_persistence.adapters.generated`, `rdf_persistence.services.generated.service`, `rdf_persistence.testkit.generated`, `rdf_persistence_generation.generated`; no hard-check problem |
| TC-39 | `grep -n "TOOLKIT_PACKAGE\|PUBLIC_PACKAGE" rdf_persistence_generation` | nothing |
| TC-40 | `make check-generated` | no diff |

Stage 3 closes like stage 1 (one review pass, L1+L3+L4).

## Stage 4: the generator's upper tiers (PR 4)

- [ ] 4.1 PD-11: `tests/generator/feature/generation.feature` from the `rp-generation` delta's
  pyramid scenario and the scenarios below, steps in `test_generation.py`. Gate:
  `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-41 | the toy copied, `rp-generate` | Python classes per module, `shapes.ttl`, `context.jsonld`, the frames, TypeScript, diagrams and `rp-manifest.json` exist |
| TC-42 | generated twice | byte-identical trees |
| TC-43 | a slot added to `books.yaml`, `rp-generate --check` | exit 1, naming `books.yaml` and the toy's regenerate command |
| TC-44 | the `description` of a class in `books.yaml` removed | a hard-check problem tagged `[description]` (`HardRule.DESCRIPTION`) naming the class; exit 1; nothing written |
| TC-45 | a toy class giving `slot_usage` to a slot annotated `toolkit_filled` | a hard-check problem tagged `[toolkit_filled]` (`HardRule.TOOLKIT_FILLED`) naming the class and slot; exit 1 |

- [ ] 4.2 PD-12: `tests/generator/integration/test_generated_artefacts.py`. Gate:
  `make test-generator`, then `make check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-46 | every `valid` instance of `tests/fixtures/conformance/` against the fresh `shapes.ttl` (pySHACL) | conforms |
| TC-47 | every `invalid` instance | does not conform; the report names the case's constraint kind |
| TC-48 | a toy `Book` JSON body, expanded with the fresh context (PyLD), then framed with the fresh `Book.frame.jsonld` | the triples carry the schema's predicate IRIs; the framed JSON equals the body |
| TC-49 | `tsc --noEmit --strict` on the fresh TypeScript | exit 0 |
| TC-50 | `PATH` without `npx` | the test fails with "install Node 20" |

- [ ] 4.3 PD-13: `tests/generator/e2e/test_generated_library_served.py`. Gate:
  `make test-containers TEST_PATH=tests/generator/e2e`, then `make check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-51 | the freshly generated `toy_e2e.generated` served on Fuseki; a librarian creates, reads, replaces and deletes a book | each answers as in `tests/e2e/test_library.py`; a read after the delete is 404 |
| TC-52 | a reader writes a book | 403 |
| TC-53 | an outsider reads the tenant | 404 |
| TC-54 | after the test | `toy_e2e` gone from `sys.modules` and `sys.path` |

- [ ] 4.4 DEC-9, PD-10: `make test-generator` adds the integration tier; the CI job installs Node;
  `develop/testing.adoc` gains the generator lane; `rp-developer-checks` delta applied by the docs.
  Gate: `make check-all`.

| ID | Input | Expected |
|---|---|---|
| TC-55 | `.github/workflows/ci.yaml` | a job `test-generator` that runs `make test-generator` after `actions/setup-node` |
| TC-56 | `make test-generator` locally | unit, feature and integration tests of `tests/generator/` run; no container starts |

Stage 4 closes with `make check-all`, `make test-containers`, the review (L1, L2, L3 apart; L4+L5
one pass), PR 4, then the reconciliation of `proposal.md` (P-0004) in PR 4 before it merges.

## Roadmap

- [x] 1.1 · [x] 1.2 · PR 1 · [x] 2.1 · [x] 2.2 · [x] 2.3 · (tester) · [x] 2.4 · [x] 2.5 · PR 2 ·
  [ ] 3.1 · PR 3 · [ ] 4.1 · [ ] 4.2 · [ ] 4.3 · [ ] 4.4 · reconcile · PR 4

## Verification

The TC tables as tests; `make check-all`, `make check-generated` and `make test-containers` before
each PR; `openspec validate generator-package --strict`; the clarity gate on this pair (≥ 9/10).
