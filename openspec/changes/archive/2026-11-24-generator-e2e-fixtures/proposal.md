<!-- Parents: issue #331. Found by aggregate-guards stage 1 (make test-containers, 2026-11-24).
     Retrospective: written on 2026-11-24 right after the fix, at the developer's request ("fix
     these errors"), as P-0020 allows for work done before its change. -->

# EPIC: the generator e2e and the restart test run against the current toy

## Appetite

**TINY.** Two test files. Test code only.

## Why

`make test-containers` fails on `develop` (#331), so no PR's full gates can come back green:

- six tests in `tests/generator/e2e/` stop at `rp-generate: --package cannot be used with 3
  [[tool.rp-generate]] entries`. Since 9bbcaefe (value modules) the toy's `pyproject.toml` has three
  targets, and `generated_toy` still renamed the package with `--package`, which the CLI allows for
  a single target only;
- `test_router.py::test_a_new_class_in_the_model_is_served_after_a_restart_with_no_code_added`
  stops at `[iri_type] Magazine: Magazine, Magazine share the type 'magazine'`. Since 6aa7a386 the
  toy has its own `Magazine`, the class the test added to prove a new class is served. Its 404
  precondition no longer held either: the toy serves `/magazines`.

## Solution outline

- `generated_toy` renames the toy's package in the copied `pyproject.toml` and in the copied
  schemas' `python_package` annotations, and generates with no flag.
- The restart test adds `Newsletter`, a class the toy does not have.

## Key decisions

- **DEC-1:** rename by rewriting the copy, not by `--package`. Rejected: allowing `--package` with
  several targets in the CLI, which would need a rule for which target it renames.
- **DEC-2:** rename the restart test's class to `Newsletter`. Rejected: removing `Magazine` from the
  toy, which 6aa7a386's tests need.

## Rabbit-holes

None.

## No-gos

- No change to the generator, the CLI or the toy.

---

## What Changes

- `tests/generator/e2e/generated_toy.py`: the copy's package is renamed in every target and module.
- `tests/integration/api/test_router.py`: the class the restart test adds is `Newsletter`.

## Capabilities

None: test code only. Archived with `--skip-specs`.
