> Derives from: EPIC `delivery-friction` (proposal.md); answers in inputs/seed.md.

One stage, one PR. Per task: the affected test directories, `make check-quality`,
`make clean-code`; `make check-all` and `make test-containers` once before the PR.

## 1. Deterministic tests

- [ ] 1.1 PD-2: the listing test compares multivalued values in any order
  (`tests/unit/entrypoints/test_listing_routes.py`, the `_unordered` helper as PD-2 defines it).
  Gate: `uv run pytest tests/unit/entrypoints -q`.
- [x] 1.2 PD-3: move the budget tests to `tests/perf/` (+ `__init__.py`), the `perf` row in
  `tests/conftest.py` and its case in `tests/unit/test_markers.py`, the `perf` marker in
  `pytest.ini`, and `make test-perf` in the `Makefile`. Gate: `make test-perf`;
  `uv run pytest tests/unit/test_markers.py -q`; `uv run pytest tests -m "unit or feature" --collect-only -q` lists no `perf` test.

## 2. Parallel tests

- [ ] 2.1 PD-8: `pytest-xdist` in the dev dependencies (`uv add --dev`), `-n auto` in
  `make test`; fix the tests that share state. Gate: two `make test` runs green, coverage ≥ 80 %;
  the two one-off random-order runs of PD-8, seeds recorded for the PR.

## 3. Formatting gate

- [ ] 3.1 PD-4: `make format-check` in `check-quality`, `make format` over the same paths; format
  the tree in its own commit (four files today: `docs/tools/check_docs.py` and three under
  `tests/unit/generation/`). Proof: plant an unformatted file once, `make check-quality` fails
  naming it; record the output for the PR, remove the file.

## 4. Testkit

- [ ] 4.1 PD-5, test first: `probe_timeout` on `wait_until` and `wait_until_async`
  (`rdf_persistence/testkit/bootstrap.py`, `tests/unit/test_testkit_bootstrap.py`): the three
  scenarios of `specs/rp-testkit/spec.md` for both helpers; the docstrings and
  `develop/testing.adoc` rule 11 mention it. Gate: `uv run pytest tests/unit/test_testkit_bootstrap.py
  tests/unit/testkit -q`.

## 5. Docs checks and guide

- [ ] 5.1 PD-7, test first: the exported-helper check in `docs/tools/check_docs.py`
  (`tests/unit/test_check_docs.py`: a planted page naming `testkit.some_helper` fails naming it; a
  submodule path such as `testkit.containers.fixtures` passes). Gate: `make check-docs`.
- [ ] 5.2 PD-6: `howto/adopt.adoc` steps 4 to 7, then a fresh cold reader given only the page
  (never the checker); each guess it reports is fixed. Gate: `make check-docs`.
- [ ] 5.3 `develop/index.adoc`: the targets table gains `make test-perf`, `make format-check` and
  `make fuseki-image`, says `make test` runs in parallel; the durations table gets the parallel
  `make test` / `make check-all` times from the stage's ordinary gate run (AGENTS.md, habits).

## 6. CI

- [ ] 6.1 PD-1: `make fuseki-image`, the fixture without `build=True` (with its comment), the cache
  step and `make fuseki-image` in the `containers` job, and the push-only warm-up job in
  `.github/workflows/ci.yaml`. Proof: the local and CI proofs of PD-1, in the PR description.

## 7. Close

- [ ] 7.1 Five review lenses, decisions in design.md, fixes; fresh checker; gates; PR; merge on
  green CI; archive.

## Roadmap

1.1 · 1.2 → 2.1 → 3.1 → 4.1 · 5.1 · 5.2 · 6.1 → 5.3 → 7.1
