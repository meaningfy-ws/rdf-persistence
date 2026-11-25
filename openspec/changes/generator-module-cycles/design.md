# Design: generator-module-cycles

> Derives from: EPIC `generator-module-cycles` (proposal.md, DEC-1 to DEC-6). Facts F-1 to F-12
> and probes P-1 to P-3: `inputs/codebase.md`. Owner questions: `inputs/qa.md` (OPEN-1 to OPEN-4);
> this PLAN is complete under their recommended answers.

## Context

`pydantic_split.render()` serialises each schema module of a target on its own (F-1). Two modules
that import each other get a top-level `from .<other> import <Class>` each, and the package fails
to import (P-1). Probe P-2 (F-3) showed the way through on hand-written pydantic 2.14 modules:
annotation-only imports under `if TYPE_CHECKING:`, and the package's `__init__.py` binding those
names into the deferring modules with `setattr` and calling `model_rebuild()`. Import order no
longer matters, nested data validates, `get_type_hints` resolves and `mypy --strict` passes.

The converter merges each import cycle into one module (F-9) only because the generator could not
do this (uml-to-linkml D-5). Its tests, report kind and docs pin the merge (F-10, F-11).

## Goals / Non-Goals

**Goals:**

- G-1: a target whose generated modules import each other generates, passes the import and type
  checks, and imports in any order (spec `rp-generation` "Modules of one target that import each
  other generate Python that loads").
- G-2: every target with no cycle writes byte-identical files (DEC-2).
- G-3: a cycle Python cannot load is refused, naming modules and classes (DEC-3).
- G-4: the converter writes one module per package; the merge and everything that names it is
  gone (DEC-4), the golden output unchanged.

**Non-Goals:** the No-gos of the EPIC; any change to the other renderers (F-6); #206 (DEC-5).

## Decisions

- **PD-1 Where the cycles are found.** On the Python import graph the step writes, not the LinkML
  `imports`: a node is a module the target generates; an edge `a -> b` is a relative
  `from .b import ...` in `a`'s first rendering. Reason: LinkML imports are transitive and the
  stock generator imports range classes it does not use (F-2), so only the written imports say
  which modules wait for which. A cycle is a strongly connected component of two or more modules.
- **PD-2 What is deferred.** In a module of a cycle, a name imported from another module of the
  same cycle is *needed at load* when it appears in the module's code anywhere but an annotation
  (a class's bases, a `Field(...)` argument such as `default_factory`, a module-level assignment
  such as a `union_of` alias); otherwise it is *deferred*. Found with `ast` on the first rendering:
  every `ast.Name` load of the name outside an annotation node (`AnnAssign.annotation`, argument
  and return annotations), outside the import statement and outside a function or lambda body
  (a body runs when called, after `__init__.py` has bound the name). Reason: it reads what the code does,
  not a list of LinkML features that could grow (F-4 lists today's three).
- **PD-3 When a cycle is refused.** The load edges (`a -> b` when `a` needs a name of `b` at load)
  among the modules of one cycle must be acyclic; if they form a cycle, `render` raises
  `SchemaGenerationError` (DEC-3) with the message
  `<a>, <b> import each other and need <A.Name>, <B.Name> while they load (a parent class, a default
  instance or a union): put these classes in one module, or break the cycle`, modules and names
  sorted. Acyclic load edges make every load order work: a module only waits at load for modules
  that never wait for it.
- **PD-4 One home for the component search.** The Tarjan search of `uml/modules.py`
  (`_visit`, `_pop_component`, `_Tarjan`, `cycle_components`) moves to a new pure module,
  `rdf_persistence_generation/module_cycles.py`, typed over any sortable hashable node; stage 1
  repoints the converter's import, stage 2 removes the converter's use. Reason: one search, in the
  generator core, where the new caller is; no copy. `module_cycles` imports only the standard
  library (`ast`, `collections.abc`) and `rdf_persistence_generation.exceptions`, never `linkml`,
  so `uml -> module_cycles` keeps the `.importlinter` contract
  `works-without-the-generate-extra`; the module is added to that contract's `source_modules`.
- **PD-5 What a module of a cycle looks like.** Its first rendering with three changes: the
  deferred names leave the top-level relative imports and are written in one block
  `if _TYPE_CHECKING:` / `    from .<b> import <Name>` (one line per module, names sorted), with
  `from typing import TYPE_CHECKING as _TYPE_CHECKING` added to the typing import (the `_` alias
  rule of #243); the module has no `model_rebuild()` footer (the package does them, PD-6).
  How it is emitted:
  - a new module model `RpModule(PydanticModule)` in `pydantic_split.py` (as `RpBaseModel`
    extends the base-model data) with two fields: `deferred: Imports | None = None` (the relative
    imports moved under the guard) and `in_cycle: bool = False`;
  - `SplitPydanticGenerator` gets `deferred: frozenset[str] = frozenset()` (the names to move);
    `before_render_template` removes them from `module.python_imports`, adds the aliased
    `TYPE_CHECKING` to the `typing` import, and returns `RpModule(**module.model_dump(), deferred=...,
    in_cycle=True)` when `deferred` or the cycle flag is set, the module unchanged otherwise;
  - an override `templates/pydantic/module.py.jinja`, a copy of the stock one (linkml's
    `pydanticgen/templates/module.py.jinja`) with two guarded additions: after
    `{{ python_imports }}`, `{% if deferred %}if _TYPE_CHECKING:` followed by
    `{{ deferred | indent(4) }}`, rendered through the stock `imports.py.jinja`; and the
    `{% include 'footer.py.jinja' %}` line wrapped in `{% if not in_cycle %}`. The stock
    `ConditionalImport` is not used: its template always writes an `else:` branch.
  A module of no cycle renders through the override with both additions off; the template's
  whitespace control keeps its text byte-identical (task 1.2's test and 1.3 check it).
- **PD-6 The package `__init__.py` of a target with a cycle.** Today the empty text. With at least
  one cycle:

  ```python
  """Completes the classes of the modules that import each other (rp-generate)."""

  from . import app_books as _app_books
  from . import app_shelves as _app_shelves

  setattr(_app_books, "Shelf", _app_shelves.Shelf)
  setattr(_app_shelves, "Plaque", _app_books.Plaque)

  _app_books.Book.model_rebuild()
  _app_books.Plaque.model_rebuild()
  _app_shelves.Shelf.model_rebuild()
  ```

  Modules sorted by name; one `setattr` per deferred name (sorted by deferring module, then name);
  one `model_rebuild()` per class of every module of every cycle, in module order then the order
  the module defines them. `setattr`, not attribute assignment: mypy's strict re-export rule
  refuses the latter (F-3). An enum has no `model_rebuild`; only classes are listed. Every
  submodule import runs this first (F-7), so a module outside the cycles that subclasses or names a
  class of a cycle loads after the cycle's classes are complete.
- **PD-7 The render loop.** `render` builds the generators as today and renders each module once
  (pass 1); `module_cycles` takes `{module name: text}` and returns the cycles, the deferred names
  per module and the refusal (PD-1 to PD-3); pass 2 re-renders only the modules of a cycle with
  their deferred names. Generation time grows by the second rendering of the modules of a cycle,
  none for a target without one.
- **PD-8 The converter after the merge** (stage 2, DEC-4). `_merge`, `_module_graph`,
  `_note_merges`, `Layout.merged` and the `merged` parameter of `choose_homes`, `shared_edges` and
  `_used_in` go; a package's module is its own path. `_settle` repeats
  `choose_homes(reachable(edges))` and `shared_edges` until the edges stop growing (they only
  grow, over a finite set, so it ends). `_module_kinds` keeps one kind per package; its "written as
  one module but have the kinds" problem goes (F-12 makes `rp-generate` refuse such a cycle).
  `ReportKind.merged_cycle` leaves `rp_generation.yaml`; `make generate` rewrites
  `rp_generation.py`. `reachable` stays in `uml/modules.py`.
- **PD-9 Tests that move or go**, each with the lane that still runs it: every test named here is
  in `tests/generator/`, run in CI by the `test-generator` job (`make test-generator`: unit,
  feature and integration tiers, slow included).

  | Test | Today | After | What still proves it |
  |---|---|---|---|
  | `integration/test_module_import_cycle.py::test_two_domain_modules_that_import_each_other_are_refused_by_the_import_check` | the cycle fails the import check | replaced (1.4) by `..._generate_and_import` | the import check's own refusals stay proved by `integration/test_generated_code_imports.py` (#242) |
  | `integration/test_module_import_cycle.py::test_the_same_two_classes_in_one_module_generate_and_import` | guards the merge fallback | removed (2.4) | nothing needed: there is no fallback |
  | `integration/test_uml_cycle.py` (both tests) | one merged module, generates | rewritten (2.4): two modules, generate and import | the spec scenario "packages that refer to each other" |
  | `unit/test_uml_rules.py` rows `_merged`, `_cycle_by_sharing`, `_kinded(..., cycle=True)` | the merge, its report line, the kinds rule | rewritten (2.2) | same rows, new expectations |
  | `feature/uml_import.feature` "Packages that refer to each other" | merged module | rewritten (2.1) | — |
  | the Tarjan search (`uml/modules.py` `cycle_components`) | no direct test today (`grep -rn cycle_components tests` is empty); covered through the converter rows | moved (1.1) | `unit/test_module_cycles.py` tests it directly |

  The lead updates `tests/audit/scenario-map.csv` rows and runs `make refresh-map` after 1.4, 2.2
  and 2.4.
- **PD-10 Spec deltas.** `rp-generation` ADDED (stage 1); `rp-uml-import` MODIFIED (stage 2). The
  first spec scenario of `rp-generation` ("a target with no cycle is written as before") is
  checked by `make check-generated` and the freshness check, not a new test (task 1.3).

## Algorithm / approach

Worked example (SPIKE-2 extended, the integration test of 1.4): `app_books` holds `Book` (a root,
slot `shelf` referring to a `Shelf`, an IRI) and `Plaque` (a part); `app_shelves` holds `Shelf`
(a root, slot `featured` referring to a `Book`, an IRI; slot `plaque`, an owned, inlined
`Plaque`). Each schema imports the other.

1. Pass 1 renders `app_books` with `from .app_shelves import Shelf` and `app_shelves` with
   `from .app_books import Book, Plaque`.
2. Graph: `app_books -> app_shelves`, `app_shelves -> app_books`; one cycle.
3. Classification: in `app_books`, `Shelf` is never named (F-2): deferred. In `app_shelves`,
   `Book` is never named and `Plaque` appears only in `plaque: _Optional[Plaque]`: both deferred.
   No load edge, so no refusal.
4. Pass 2: `app_books` gets `if _TYPE_CHECKING: from .app_shelves import Shelf`; `app_shelves`
   gets `if _TYPE_CHECKING: from .app_books import Book, Plaque`; neither has a footer rebuild.
5. `__init__.py` as in PD-6, with three `setattr` lines (`Shelf` into `app_books`; `Book`,
   `Plaque` into `app_shelves`) and the three rebuilds.
6. `import cycle_app.domain.generated.app_shelves` runs `__init__` (loads both, binds, rebuilds),
   then returns the complete module. `Shelf(id=..., label=..., plaque={...})` validates `plaque`
   into a `Plaque`.

Counter-example (refused): `app_a.Child is_a app_b.Base`, `app_b.Other is_a app_a.Root`. Load
edges `app_a -> app_b` (Base) and `app_b -> app_a` (Root) form a cycle, so `render` raises:
`app_a, app_b import each other and need app_a.Root, app_b.Base while they load (a parent class, a
default instance or a union): put these classes in one module, or break the cycle`.

Half-eager cycle (loads): `app_a.Child is_a app_b.Base` and `app_b.Holder.a: Optional[Root]` with
`Root` in `app_a`. Load edge only `app_a -> app_b`; `Root` deferred in `app_b`. Importing `app_a`
first: it imports `app_b` (which waits for nothing), then defines `Child`. Importing `app_b` first:
`__init__` has already loaded both. Either way `__init__` binds `Root` into `app_b` and rebuilds.

Idempotency: rendering is a pure function of the schemas; two runs give the same text (the
`rp-generation` reproducibility requirement holds; sorted orders in PD-5 and PD-6).

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Edit the serialised module text with regular expressions | Render through the hooks and templates (PD-5); use `ast` only to read | A text edit breaks on the next stock-template change and hides in no test |
| Defer every import between generated modules | Defer only within a cycle (DEC-2) | Every committed generated file would change |
| Bind names with `_mod.Name = ...` | `setattr(_mod, "Name", ...)` | mypy strict refuses the former (F-3) |
| Call `model_rebuild()` in a cyclic module's footer | Only in `__init__.py` | It raises while the other module's class is unbound |
| Merge a load-time cycle into one module in the generator | Refuse it (DEC-3) | It silently moves classes between modules |
| Keep a "merge" switch in the converter | Remove the merge (DEC-4) | Two layouts to test and document for one bug that is fixed |
| Hand-write a lazy import (`if TYPE_CHECKING:`) or an `__init__.py` rebuild in a module of no cycle, or in a test fixture's generated package | Leave lazy imports to the generator, which writes them only inside a cycle (DEC-2) | The file is generated (AGENTS principle 2): the freshness check flags the edit and the next `make generate` erases it |
| Use `_types_namespace` instead of binding | Bind, then rebuild | `get_type_hints` and pydantic's lazy rebuild read the module's globals (F-3) |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Two modules need each other's classes at load (PD-3) | `module_cycles` finds a cycle in the load edges | `SchemaGenerationError` -> `python:` problem, exit 1, files left as they were; test 1.4 |
| A name is used at load in a form PD-2 misses (a decorator, a class keyword, a default value expression) | `ast` sees every `Name` load outside annotations, so it is classed as needed at load | loads or is refused, never deferred wrongly; unit test with a `default_factory` and a union alias (1.1) |
| A deferred name is used inside a validator or other function body | PD-2 skips function and lambda bodies | deferred; bound before any call can run (`__init__.py` runs before the module is handed out); unit test `test_a_name_used_in_a_function_body_is_deferred` (1.1) |
| A module of the root schema (FULL mode) is in the cycle (a module imports a class the root declares) | it is a node like any other (PD-1) | same handling as any module of the cycle |
| A module of the cycle imports another cycle member's enum | enum used in annotations only: deferred and bound; an enum used as a default value: needed at load | as the row above; no `model_rebuild` for an enum (PD-6) |
| `__init__.py` imports a module whose import fails for another reason (MRO #242, a shadowed name #243) | the import check runs on what was written | `import check` problem naming the module, as today |
| A target with a cycle whose `__init__.py` folder is shared with another target | not expected: each target has its own package folder (`python_folder`); `render` already writes `__init__.py` per target | if two targets wrote one folder, the second `__init__.py` would overwrite the first; the import check then fails naming the module (RISK-4) |
| A consumer imports a cyclic module by file path, bypassing the package | not detectable | unsupported, as for any generated package; documented in the user manual (1.5) |
| The stock generator changes its footer or imports template on a LinkML upgrade | the byte-identity check of the toolkit's generated files (`make check-generated`) and test 1.2 | fix the override; RISK-2 |
| Converter: a slot's home chosen differently once modules are no longer merged | golden tests `test_uml_golden.py` (no cycle in the golden model) and the `_cycle_by_sharing` row | new home recorded in the row (2.2) |
| Converter output with packages of different kinds in a cycle | `rp-generate`'s boundary check (F-12) | the conversion succeeds with each kind kept (unit row, 2.2); `rp-generate` on that output exits 1 naming the domain module and the access one (integration test `test_a_converted_cycle_between_kinds_is_refused_by_the_boundary_check`, 2.4) |
| A consumer imports a deferred name from the module that defers it (`from .app_books import Shelf`, `Shelf` declared in `app_shelves`) | mypy `--strict` (not re-exported); at run time it works once `__init__.py` bound it | documented: import a class from its own module or from the root module (1.5) |
| Converter output with inheritance both ways between two packages | `rp-generate`'s python step (PD-3) | refused naming modules and classes; documented in the UML conventions problems table (2.5); RISK-1 |

## Risks / Trade-offs

- **RISK-1 The consumer's model has an inheritance cycle between packages** (a class's parent in
  another package whose classes inherit back). Likelihood: low (the consumer's acceptance run had
  one merged component, of unknown kind). Impact: medium: today the merge hides it; after stage 2
  `rp-generate` refuses it until the model is changed. Mitigation: the refusal names the classes
  and the conventions page says how to fix it; the lead asks the consumer to convert and generate
  its current model with the stage 2 branch before the merge (acceptance step in 2.6), and reports
  a refusal to the owner before merging (OPEN-2 decides whether the converter then keeps a narrow
  merge).
- **RISK-2 The overrides ride on the stock templates.** A LinkML upgrade can change the footer or
  imports block. Likelihood: medium over time; impact: low, caught by `make check-generated` and
  test 1.2. Accepted.
- **RISK-3 BREAKING converter output** (DEC-4): a consumer that converted a cyclic model gets
  classes in new modules. Likelihood: certain for such a consumer; impact: its imports of the
  moved classes change. Mitigation: `CHANGELOG.md` **BREAKING** entry naming the old and new
  layout; the root module still imports every class (unchanged), so imports through the root keep
  working.
- **RISK-4 Two targets in one package folder** overwriting `__init__.py`. Likelihood: very low (no
  such configuration in the repository). Accepted; the import check catches the effect.
- **RISK-5 Conflict with `converter-hardening`** in `uml/convert.py`. Likelihood: high if both run
  at once. Mitigation: stage 2 merges first (proposal Rabbit-holes); in `uml/` stage 1 only moves
  the Tarjan search out of `uml/modules.py` and changes the import of `cycle_components` at
  `uml/convert.py:49` to `rdf_persistence_generation.module_cycles` (PD-4).
- **RISK-6 The whole-model start-up check on a cyclic output** (converter-hardening's RISK-4,
  added by the owner 2026-11-24). `uml/write.py` loads the staged root schema with `load_schema`
  (a `SchemaView`) before it moves the files; once stage 2 writes modules that import each other,
  that load must follow a cyclic import. Likelihood low (`SchemaView` keeps a visited set); impact:
  a converter run that writes a workflow would fail on any cyclic model. Mitigation: the test of
  task 2.4 re-runs the check on a cyclic pair.
- **Trade-off:** pass 2 re-renders the modules of a cycle (PD-7): time for cyclic targets only.

## Delivery decisions

- **D-1 (stage 1, task 1.1) The cycle analysis result is a LinkML class.** The model guard
  (`tests/unit/testkit/test_model_guard.py`) refuses a hand-written `NamedTuple` or dataclass;
  `CycleAnalysis` is a generator-technical record (P-0011), so it is declared in
  `rdf_persistence_generation/model/rp_generation.yaml` and generated into `rp_generation.py`;
  the analysis' private helper record goes the same way or becomes plain local data. Rejected:
  listing it in the guard's `HAND_WRITTEN` (kept for types that hold foreign runtime objects).
  Task 1.3's byte identity covers the targets' generated output, not `rp_generation.py`.
- **D-2 (stage 1) No `make test-containers` for stage 1.** Stage 1 changes no adapter (only the
  generator, its templates and tests); `AGENTS.md` runs the container suite when adapters change.
  Task 1.6's line naming it is read under that rule; stage 2 changes no adapter either.
- **D-3 (stage 1) The pre-commit GitNexus re-index was skipped.** `make reindex` failed while
  another session's GitNexus process held the graph DB; the documented recovery
  (`gitnexus clean --force`) would remove the index under that session. The stage's symbols did
  not move from the stage-start impact (LOW: `cycle_components` one caller, `render` one caller in
  `steps.py`), and `make check-all` covers the callers.
- **D-4 (stage 1) The stage review is one L2+L3 pass** (owner's rule P-0005, `develop/agents.adoc`
  *Keeping the challenge cheap*), not the MEDIUM default of two grouped runs; the full review
  (L1, L2, L3 apart, L4+L5 as one) runs once at the end of stage 2 (task 2.6).
- Stage 1 review, under the floor (no Critical finding; not fixed in this stage):
  - W1 (L2) the refusal test does not assert the `python` step nor that existing generated files
    are left as they were (spec scenario 3).
  - S1 (L2) the `first` parameter of the two load-order tests cannot change the load order (the
    package `__init__.py` always loads the cycle first).
  - S2 (L3) `module_cycles` relies on `from __future__ import annotations` in the stock output and
    does not check for it; the integration tests that import a generated cycle would fail if a
    LinkML upgrade dropped it (RISK-2).
  - S3 (L2) the docs say only annotation names are deferred and write `TYPE_CHECKING` unaliased;
    the code also defers unused names and names read only in function bodies, under
    `_TYPE_CHECKING`.
- **D-5 (owner, 2026-11-25) W1 is fixed in stage 2.** The refusal test of a cycle Python cannot
  load also asserts the `python:` problem line and that generated files already written are left
  byte-identical (spec `rp-generation` scenario 3, in full); task 2.4. The owner answered OPEN-1,
  OPEN-2 and OPEN-4 as recommended (`inputs/qa.md`, *Owner's answers*).
- **D-6 (stage 2) Tasks 2.1, 2.2 and 2.3 go to one builder.** 2.1 and 2.2 are the failing tests
  2.3 turns green; one builder writes them, sees them fail, then removes the merge, so no hand-off
  sits between a failing test and its code. 2.4 and 2.5 run as two builders in parallel
  (disjoint files). The stage's mark carries `risk=recorded` (RISK-1, RISK-5 and RISK-6 name its
  files); the full review of task 2.6 names them as its focus.
- **D-7 (stage 2) RISK-1 checked by the lead on the consumer's model, read-only.** The consumer's
  committed tree (its `HEAD` `558cc82`, extracted with `git archive` into a scratch folder, its
  repository untouched) was converted with its own `convert-model` arguments, once with this
  branch's toolkit (`2c6936eb`) and once with `develop` before stage 2 (`f4ecc5e4`): the two
  outputs are identical (its current report has no `merged-cycle` line: the model has no package
  cycle), and `rp-generate` on the stage 2 output generates both targets with no problem. So no
  `python:` refusal and no change for this consumer from stage 2; the 13 added lines against its
  committed models (`required: false` flags) come from `develop`'s earlier converter work, not
  from this change.
- **D-8 (stage 2) Stage-end impact from `detect_changes` on the stage-start index.** `make
  reindex` failed in its embeddings step (a duplicated primary key in `CodeEmbedding`); the
  stage-start index was fresh (`f4ecc5e4`). `detect_changes` against `origin/develop`: risk
  MEDIUM, every changed symbol in `uml/` and its tests, the two `share` flows affected, both
  covered by the UML rules and golden tests in `make check-all`.

## Open Questions

None blocking; owner questions with defaults are `inputs/qa.md` OPEN-1 to OPEN-4.
