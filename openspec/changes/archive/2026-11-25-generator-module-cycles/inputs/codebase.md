# Codebase analysis and probes (secondary; never groomed)

The planner's reading of the worktree at `25e23156` (develop), 2026-11-22. Facts are cited F-n in
the PLAN.

## Facts

- **F-1 Where the cycle breaks.** `extensions/pydantic_split.py` `render()` builds one
  `SplitPydanticGenerator` per schema module beside the root and serialises each on its own. The
  stock module template writes every class import at the top (`from .app_shelves import Shelf`)
  and the stock footer ends each module with `<Class>.model_rebuild()` for each of its classes.
  `from __future__ import annotations` defers annotations, not imports.
- **F-2 Probe P-1 (today's output).** The SPIKE-2 project (`test_module_import_cycle.py`'s
  `_write_project`, `app_books` <-> `app_shelves`) generated into `$TMPDIR`: exit 1, three
  `import check` lines (`app`, `app_books`, `app_shelves`), each a circular `ImportError`. In
  `app_books.py`, `Shelf` is imported but not used: `shelf` is a reference to another aggregate,
  so its field is `Optional[str]`. The stock generator imports a range class whether or not the
  field names it.
- **F-3 Probe P-2 (the lazy pattern works).** Two hand-written pydantic 2.14 modules, each
  importing the other's class only under `if TYPE_CHECKING:`, each field typed by the other's class
  (inlined both ways), each module ending `X.model_rebuild(raise_errors=False)`; the package
  `__init__.py` imports both modules, binds each deferred name into the module that defers it
  (`setattr(_app_books, "Shelf", _app_shelves.Shelf)`) and calls `model_rebuild()` on both classes.
  Result: importing either module first works; nested dicts validate into the right classes both
  ways; `model_json_schema()` holds both definitions; `typing.get_type_hints(Shelf)` resolves;
  `mypy --strict` passes. A plain attribute assignment (`_app_books.Shelf = ...`) fails mypy strict
  (`does not explicitly export attribute`); `setattr` passes. Without the binding, a
  `model_rebuild(_types_namespace=...)` also works, but `typing.get_type_hints` then fails. The same modules with the alias
  `from typing import TYPE_CHECKING as _TYPE_CHECKING` and `if _TYPE_CHECKING:` also pass
  `mypy --strict`.
- **F-4 What needs a name at import time.** In a generated module a class name is needed when the
  module runs (not only in annotations) as an `is_a` parent or mixin base (the class statement), as
  a `Field(default_factory=<Range>)` (`default_instance`), and in a `union_of` type alias
  (`after_generate_class`, `type_alias_value`). Python cannot load two modules whose classes need
  each other at import time, whatever the import style.
- **F-5 No downstream reads annotations.** No module of `rdf_persistence` or
  `rdf_persistence_generation` outside `generated/` calls `typing.get_type_hints`,
  `__annotations__` or `inspect.get_annotations`.
- **F-6 The other renderers accept a cycle.** In P-1 the shapes, context, frames, OpenAPI
  components and TypeScript steps all ran; the TypeScript modules import with `import type`, which
  allows cycles. LinkML's `SchemaView.imports_closure` tolerates import cycles.
- **F-7 The import check** (`checks/importable.py`, #242) imports every module of the target in a
  subprocess and type-checks it with `mypy-generated.ini` (pydantic plugin, `check_untyped_defs`).
  Importing a submodule runs the package's `__init__.py` first.
- **F-8 The toolkit's own targets have no cycle**: 25 targets in `pyproject.toml`, none with two
  generated modules that import each other (P-1 was the first cycle generated anywhere).
- **F-9 The converter's merge** (`uml/convert.py`): `_merge` maps each package path to the first
  path of its strongly connected component (`uml/modules.py` `cycle_components`, a Tarjan search);
  `_module_graph` and `Layout.merged` carry that map; `_settle` repeats `choose_homes` +
  `shared_edges` until the merge stops changing; `_note_merges` writes `merged-cycle` report lines;
  `_module_kinds` refuses a merged module whose packages have different `module_kind`s.
  `ReportKind.merged_cycle` is a value of `rp_generation.yaml`. `reachable` (same file) is still
  needed by `choose_homes`.
- **F-10 Tests that pin the merge:** `tests/generator/unit/test_uml_rules.py` rows "two packages
  that refer to each other are written as one module (D-5)" (`_merged`), "a cycle that sharing
  creates is merged into one module, from the final imports (D-5)" (`_cycle_by_sharing`), "failure:
  packages written as one module with different kinds name the module" (`_kinded(..., cycle=True)`);
  `tests/generator/integration/test_uml_cycle.py` (IT-2, two tests);
  `tests/generator/feature/uml_import.feature` scenario "Packages that refer to each other";
  `tests/generator/integration/test_module_import_cycle.py` (two tests: the refusal by the import
  check, and the merged control). The golden fixtures (`tests/generator/fixtures/uml/golden/`)
  hold no `merged-cycle` line.
- **F-11 Docs and specs that state the merge:** `rp-uml-import` requirement "A UML class model
  converts to toolkit-conformant LinkML" (its text and scenario "packages that refer to each
  other"); `reference/uml-conventions.adoc` `#packages`, `#module-kind`, `#shared-slots` and the
  problems table row on `module_kind`; `howto/uml-to-linkml.adoc` lines 78 and 169 (the report
  kinds); `CHANGELOG.md` `[0.8.1]` line 36 ("an unknown value, or merged packages with
  different kinds, fail the run") for the merge, and line 25 ("including two modules that import
  each other (#208)") for the generator's refusal. Both are in the released `[0.8.1]` section,
  which is never edited: the change adds `[Unreleased]` entries that state what they supersede.
- **F-13 Import contract.** `.importlinter` `works-without-the-generate-extra` lists
  `rdf_persistence_generation.uml` among the modules that must not reach `linkml`; anything the
  converter imports must import no `linkml` either.
- **F-14 Parts across modules.** The hard check's `described` rule (`checks/hard.py`
  `_described_problems`) takes the owned classes from `schema_structure.owned_classes` over all
  own classes of the target, and `checks/boundary.py` has no rule on the module a part is declared
  in: a part may sit in another module than its root.
- **F-12 The domain boundary.** `checks/boundary.py` refuses a domain module that imports a
  `technical` or `access` module (`FORBIDDEN_FOR_DOMAIN`). A cycle between a domain package and an
  access package therefore always has a refused edge, once the converter writes them apart.

## Probe P-3 (#206's check against today's schemas)

Every slot of each closure, grouped by its expanded `slot_uri`: the 25 toolkit targets and
`tests/fixtures/library/library.yaml` have no two slots on one IRI. The converter's golden output
`tests/generator/fixtures/uml/golden/stage2/library.yaml` has one: `identifier`
(`dcterms:identifier`, `library_catalogue`) and the toolkit's `id` (`dcterms:identifier`,
`rp_core`). The converter keeps that attribute on purpose
(`test_uml_toolkit.py::test_the_identifier_slot_is_not_offered_for_reuse`). So #206's check would
refuse the converter's own golden output unless identifier slots are exempt, a decision #206 does
not make (see `qa.md` OPEN-1).

Probe scripts: the session scratchpad (`probe_cycle.py`, `probe_slot_uri.py`) and `$TMPDIR/lazy/`
for P-2; not kept in the repository.
