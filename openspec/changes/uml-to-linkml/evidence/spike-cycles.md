# SPIKE-2: do cyclic module imports generate? (PD-14)

Date: 2026-11-20. Base: `8f64ccd9`. Decision D-2 (the spike runs on hand-written modules, without
the converter).

## Verdict

**No.** `rp-generate` accepts two `module_kind: domain` modules that import each other (exit 0,
"generated 1 target(s), no problems"), but the generated Python package does not import: the
split pydantic modules import each other at module level and fail with a circular `ImportError`.

**PD-14 branch: the packages of each import cycle are written as one module** (PD-27, report line
`merged-cycle`). Modules do not stay one per package where a cycle exists.

## Steps

A project in `tmp_path` with `[tool.rp-generate]` (`schema = "app.yaml"`, package
`cycle_app.domain.generated`, a `migrations` folder), a root schema `app.yaml` (with a quoted
`version`) importing two hand-written domain modules:

- `app_books`: `Book` (`AggregateRoot`, `Described`, `rp_path`), slot `shelf` -> `Shelf`; imports
  `app_shelves`.
- `app_shelves`: `Shelf` (`AggregateRoot`, `Described`), slot `featured` -> `Book`; imports
  `app_books`.

Then `rp-generate --project <pyproject>` (write mode), import
`cycle_app.domain.generated.app_books`, build one `Book` with a `shelf`.

| Step | Result |
|---|---|
| lint, boundary, hard checks | pass (after the project setup of the toy: a layer before `generated` in the package, a `migrations` folder, a root `version`; these are setup errors of the first run, not cycle errors) |
| renderers, pydantic split | run; exit 0, `generated 1 target(s), no problems` |
| Python import of the package | **fails** |

## Command and result

```
uv run pytest tests/generator/integration/test_module_import_cycle.py -q --runxfail \
  -o rp_generate_projects=pyproject.toml
```

(`-o rp_generate_projects=pyproject.toml` drops the toy library from the session freshness check;
it was stale only because another builder's `books_activities.yaml` edit was in flight.)

The exact error, from the cycle test:

```
cycle_app/domain/generated/app_books.py:35: in <module>
    from .app_shelves import Shelf
cycle_app/domain/generated/app_shelves.py:35: in <module>
    from .app_books import Book
ImportError: cannot import name 'Book' from partially initialized module
'cycle_app.domain.generated.app_books' (most likely due to a circular import)
```

Cause: F-10, the split generation writes a plain `from .<other> import <Class>` into each module
(after `from __future__ import annotations`, which does not defer imports); two modules that
import each other cannot both finish loading.

## The fallback works (PD-27)

The same two classes and both slots as ONE module (`app_books`, no import of the other) generate
(exit 0) and import, and one `Book` with a `shelf` is built: the control test passes.

## Tests

`tests/generator/integration/test_module_import_cycle.py`:

- `test_two_domain_modules_that_import_each_other_generate_and_import`:
  `xfail(strict=True, raises=ImportError)`. It turns into a failure (XPASS strict) the day the
  generator learns cycles; then PD-14's first branch applies and PD-27 can go.
- `test_the_same_two_classes_in_one_module_generate_and_import`: passes; guards the fallback.

## Upstream finding (ours)

`rdf_persistence_generation` pydantic split: modules that import each other produce a circular
`ImportError`. Reproduction: the cycle test above. A generator fix (a deferred import,
`TYPE_CHECKING` plus model rebuild, or one module per strongly connected component) is outside this
spike; the PLAN's fallback applies in the converter.
