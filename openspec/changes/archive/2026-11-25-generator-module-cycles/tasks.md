EPIC: generator-module-cycles (proposal.md). Decisions: DEC-1 to DEC-6 (proposal), PD-1 to PD-10 (design.md).

> Derives from: EPIC `generator-module-cycles`.

Every task: test-first (its first failing test is named; write it, see it fail for the stated
reason, then the code); task gate `make test-changed check-quality`; commit body
`Refs: generator-module-cycles <task> <PD>` (`Refs: #208` on stage 1's last commit). Builders
never commit; the lead does and ticks this file. Builders never edit
`tests/audit/scenario-map.csv`; the lead adds rows and runs `make refresh-map` (PD-9). All tests
named here run in CI's `test-generator` job (`make test-generator`).

## 1. Stage 1: the generator loads module cycles (#208) — branch `change/generator-module-cycles-1`, one PR

- [x] 1.1 **unit** — PD-1 to PD-4. New pure module `rdf_persistence_generation/module_cycles.py`:
  the Tarjan search moved from `uml/modules.py` (generic over sortable nodes; `uml/convert.py`
  imports it from here), and the analysis of `{module name: rendered text}` returning the cycles,
  the deferred names per module, and raising `SchemaGenerationError` (PD-3's message) on a load
  cycle. First failing test: `tests/generator/unit/test_module_cycles.py::test_two_modules_that_import_each_other_are_one_cycle`
  (two texts with relative imports of each other's class -> one cycle of both; fails on the
  missing module). Then, same file: `test_a_name_used_only_in_annotations_is_deferred`,
  `test_a_base_class_from_the_cycle_is_needed_at_load`,
  `test_a_default_factory_and_a_union_alias_are_needed_at_load`,
  `test_an_imported_name_never_used_is_deferred` (F-2),
  `test_a_name_used_in_a_function_body_is_deferred`,
  `test_a_load_cycle_is_refused_naming_the_modules_and_the_classes` (asserts the module names and
  the class names appear, not the wording),
  `test_a_half_load_cycle_is_accepted` (load edge one way only),
  `test_modules_in_no_cycle_have_nothing_deferred`, `test_an_absolute_import_is_not_an_edge`
  (a module of another target, imported by its package, is never part of a cycle). No test imports
  `cycle_components` today, so none is repointed. `module_cycles` imports no `linkml` (PD-4); add
  `rdf_persistence_generation.module_cycles` to `source_modules` of the `.importlinter` contract
  `works-without-the-generate-extra`. Accept: the file passes; `make check-architecture` green
  (part of `make test-changed check-quality`, green).
- [x] 1.2 **unit** — PD-5 to PD-7, after 1.1. `pydantic_split.render` two passes; `RpModule`
  (fields `deferred: Imports | None`, `in_cycle: bool`) and the generator field `deferred`; the
  override `templates/pydantic/module.py.jinja` (the stock template plus the guarded
  `if _TYPE_CHECKING:` block and the footer include under `{% if not in_cycle %}`); the
  `__init__.py` text of PD-6. First failing test: `tests/generator/unit/test_ext_pydantic_split.py::test_a_module_in_a_cycle_imports_the_other_modules_class_for_the_type_checker_only`
  (renders a two-module cycle written in `tmp_path`; asserts the class import sits under
  `if _TYPE_CHECKING:`, not at the top, and the module has no `model_rebuild` line). Then:
  `test_the_package_init_of_a_target_with_a_cycle_binds_and_rebuilds` (asserts the `setattr`
  lines and one `model_rebuild()` per class, in PD-6's order),
  `test_a_target_with_no_cycle_writes_an_empty_init_and_the_stock_footer`,
  `test_two_renders_of_a_cycle_are_identical` (reproducibility). Accept: as 1.1.
- [x] 1.3 **byte identity (no new test)** — DEC-2, PD-10. After 1.2, `make generate`, then
  `git status --porcelain` lists no generated file of the toolkit or of `tests/fixtures/`; the lead
  runs `make check-generated` after committing 1.2. Accept: both empty / green; any diff stops the
  stage and goes to the lead.
- [x] 1.4 **integration** — G-1, G-3, spec `rp-generation` scenarios 1 and 3, after 1.2. In
  `tests/generator/integration/test_module_import_cycle.py`: replace
  `test_two_domain_modules_that_import_each_other_are_refused_by_the_import_check` by the first
  failing test `test_two_domain_modules_that_import_each_other_generate_and_import`, parametrised
  over which module is imported first (`app_books`, `app_shelves`): write mode and `--check` exit
  0; `Shelf` gets an owned `Plaque` part declared in `app_books` (design *Algorithm*) and is built
  from nested data whose `plaque` becomes a `Plaque`. The part: `Plaque` (in `app_books`) has
  `mixins: [Described]` and no `AggregateRoot`; the slot `plaque` (in `app_shelves`, on `Shelf`)
  has `range: Plaque`, `inlined: true` and `annotations: {owned: true}`. The hard check finds owned
  classes over every own module of the target (`schema_structure.owned_classes` via
  `checks/hard.py` `_described_problems`, rule `HardRule.DESCRIBED`: "a root or owned class
  includes Described"), not per module, so a part declared beside another module's root passes;
  the test's first assertion is that the run reports no `hard check` line (write mode exit 0).
  Then
  `test_a_parent_in_one_module_and_a_reference_back_load_in_any_order` (the half-load cycle) and
  `test_two_modules_whose_classes_inherit_from_each_other_are_refused` (exit 1, the error names
  both modules and both parents, no generated module written). Leave
  `test_the_same_two_classes_in_one_module_generate_and_import` for 2.4. Accept: the file passes;
  `make test-generator` green.
- [x] 1.5 **docs** — after 1.4. `architecture/generation.adoc` (the `pydantic_split.py` row of the
  artefacts table, and *Correctness of the generated code*: what a cycle generates, what is
  refused), `user-manual/generate.adoc` (the Python output row: a cycle's `__init__.py`; import the
  package, never a file by path; import a class from its own module or from the root module, never
  from a module of the cycle that only names it (`from .app_books import Shelf` runs but fails
  `mypy --strict`); the refusal message and its two fixes), `CHANGELOG.md` *Fixed*
  (#208) under `[Unreleased]` only, saying it replaces the refusal of two modules that import each
  other described in `[0.8.1]`; released sections are never edited. The `rp-generation` delta of this change is already written. Accept: `make check-docs`
  green.
- [x] 1.6 **lead** — `make check-all`, `make test-containers`; the stage pass (L2+L3, one pass);
  accepted findings into design.md; PR into `develop`, merged on green CI; #208 closed by it.

## 2. Stage 2: the converter stops merging — branch `change/generator-module-cycles-2` off `develop` after stage 1 merged, one PR

- [x] 2.1 **feature** — spec `rp-uml-import` "packages that refer to each other". In
  `tests/generator/feature/uml_import.feature`, the scenario's Thens become: "Then the conversion
  succeeds", "And the packages are written as the modules "app_books" and "app_shelves" that import
  each other", "And the report has no line about a cycle". First failing test: that scenario
  (`test_uml_import.py`), failing on the one merged module; the old `merged-cycle` step goes.
  Accept: fails for that reason before 2.3, passes after.
- [x] 2.2 **unit** — PD-8, spec scenario "packages of different kinds that refer to each other".
  In `tests/generator/unit/test_uml_rules.py`: row "two packages that refer to each other are
  written as one module (D-5)" becomes the first failing test
  `two packages that refer to each other are two modules that import each other` (asserts
  `app_library` and `app_shelves`, each import list naming the other, the root importing both,
  no report line of the merge); row "a cycle that sharing creates is merged ..." becomes "a cycle
  that sharing creates leaves each package its own module" (`app_afirst`, `app_bhome`, `app_zed`;
  `has_parent` defined in `app_bhome`, the module `app_afirst` reaches; `app_bhome` and `app_zed`
  import each other); row "failure:
  packages written as one module with different kinds ..." becomes "packages of different kinds
  that refer to each other keep their own kinds" (`_kinds(app_library="access",
  app_shelves="domain")`, no problem). Accept: as 2.1.
- [x] 2.3 **code** — PD-8, DEC-4, after 2.1 and 2.2. Remove the merge from `uml/convert.py`
  (`_merge`, `_module_graph`, `_note_merges`, `Layout.merged`, `_settle`'s new end condition,
  `_module_kinds`' merged-kinds problem) and the `merged` parameters in `uml/slots.py`; remove the
  converter's import of the Tarjan search; remove `merged_cycle` from `ReportKind` in
  `rdf_persistence_generation/model/rp_generation.yaml`, then `make generate`. Accept: 2.1 and 2.2
  pass; `tests/generator/unit/test_uml_golden.py` passes with the golden files unchanged
  (`git status` shows no change under `tests/generator/fixtures/uml/golden/`); `grep -rn
  "merged_cycle\|MERGED_CYCLE\|cycle_components" rdf_persistence_generation/uml` is empty;
  `make test-changed check-quality` green.
- [x] 2.4 **integration** — after 2.3. Rewrite `tests/generator/integration/test_uml_cycle.py`:
  first failing test `test_the_packages_of_a_cycle_become_two_modules_that_import_each_other`
  (two modules, each import list naming the other, the report has no `merged-cycle` line), then
  `test_the_converted_cycle_generates_and_the_package_imports` (`rp-generate` exit 0; a `Book`
  with a `shelf` is built from `app_books`, imported after `app_shelves`), then
  `test_a_converted_cycle_between_kinds_is_refused_by_the_boundary_check` (spec scenario
  "packages of different kinds that refer to each other": a `.qea` with `library` tagged
  `module_kind=access` and `shelves` domain, linked both ways; `rp-uml2linkml` exit 0, then
  `rp-generate` exit 1 with a `boundary check` line naming `app_shelves` and `app_library`). Remove
  `test_module_import_cycle.py::test_the_same_two_classes_in_one_module_generate_and_import`
  (PD-9). Then (RISK-6, converter-hardening's RISK-4) in `tests/generator/unit/test_uml_write.py`:
  `test_the_start_up_check_loads_modules_that_import_each_other`, the whole-model start-up check
  of `test_the_start_up_check_refuses_a_staged_workflow` re-run with the root schema importing two
  modules that import each other (one class of each naming a workflow, the two sharing a class
  IRI): `write` raises `StagedFileRefused` naming both workflows, so `load_schema` followed the
  cyclic imports to the classes. Then (D-5, stage 1's W1) in
  `tests/generator/integration/test_module_import_cycle.py`, strengthen
  `test_two_modules_whose_classes_inherit_from_each_other_are_refused`: generate the two modules
  once without the inheritance cycle, add it, run again, and assert exit 1, a `python:` problem
  line, and every generated file byte-identical to the first run's. Accept: `make test-generator`
  green.
- [x] 2.5 **docs** — after 2.3. `reference/uml-conventions.adoc`: `#packages` (one module per
  package; packages that refer to each other give modules that import each other),
  `#module-kind` (the merged-kinds failure removed; a cycle between kinds is refused by
  `rp-generate`'s boundary check), `#shared-slots` (no merge), the problems table (the `module_kind`
  row; a new row: classes inheriting both ways between two packages, refused by `rp-generate`,
  fix by moving them into one package); `howto/uml-to-linkml.adoc` (lines 80 and 186: the
  `merged-cycle` kind removed); `CHANGELOG.md`: only a **BREAKING** entry under `[Unreleased]` (DEC-4,
  RISK-3) stating that the merge of packages that refer to each other, and the failure of merged
  packages with different kinds, described in `[0.8.1]`, are removed; old and new layout; imports
  through the root module unchanged. Released sections are never edited. Accept: `make check-docs` green;
  `grep -rn "merged-cycle" docs` empty.
- [x] 2.6 **lead** — acceptance: the converter's cyclic library (2.4) shown converting, generating
  and importing; RISK-1: ask the consumer to convert and generate its current model on this branch
  and report any `python:` refusal to the owner before the merge (OPEN-2). Then `make check-all`,
  `make test-containers`, the full review once (MEDIUM, rule P-0005: L1, L2, L3 apart, L4+L5 as
  one), accepted findings into design.md, PR into `develop` merged on green CI.

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 1.4 · [ ] 1.5 · [ ] 1.6 (stage 1 PR merged)
- [ ] 2.1 ∥ [ ] 2.2 · [ ] 2.3 · [ ] 2.4 ∥ [ ] 2.5 · [ ] 2.6 (stage 2 PR merged)

## Verification

Each stage: its tests first-failing then green in `make test-generator`; `make check-all`
(includes `openspec validate --all --strict`) and `make check-generated` green; stage 1 changes no
existing generated file, stage 2 no golden file; the clarity gate on this PLAN ≥ 9/10 (or accepted
under R-0005) before 1.1.
