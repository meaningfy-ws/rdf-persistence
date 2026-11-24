# Design: generator-e2e-fixtures

> Derives from: EPIC `generator-e2e-fixtures` (`proposal.md`, #331). DEC-1 and DEC-2 are cited, not
> restated.

## Context

- `rdf_persistence_generation/config.py` `_refuse_unusable` refuses any flag with more than one
  `[[tool.rp-generate]]` row.
- The toy's `values/loan_checks.yaml` and `services/loan_checks_response.yaml` name their
  `python_package` under `tests.fixtures.library`, so a renamed copy must rename them too.
- `hard.py` `_iri_type_problems` counts every own class; the toy's `books.yaml` and the test's
  module both defined `Magazine`.

## Decisions

### PD-1

`generated_toy` replaces `tests.fixtures.library` with `toy_e2e` in the copy's `pyproject.toml` and
`*.yaml` files, then runs `rp-generate --project` alone (DEC-1).

### PD-2

The restart test's module, class, path and names use `Newsletter` / `newsletters` (DEC-2).

## Verification

The six e2e tests and the restart test, red on `develop` at 3745e85c, pass:
`uv run pytest tests/generator/e2e/ tests/integration/api/test_router.py::test_a_new_class_in_the_model_is_served_after_a_restart_with_no_code_added`
(7 passed).
