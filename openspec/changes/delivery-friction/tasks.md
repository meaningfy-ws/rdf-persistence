> Derives from: EPIC `delivery-friction` (proposal.md); answers in inputs/seed.md.

One stage, one PR. Per task: the affected test directories, `make check-quality`,
`make clean-code`; `make check-all` and `make test-containers` once before the PR.

## 1. Deterministic tests

- [ ] 1.1 PD-2: the listing test compares multivalued values in any order
  (`tests/unit/entrypoints/test_listing_routes.py`).
- [ ] 1.2 PD-3: move the budget tests to `tests/perf/`, the `perf` marker and `make test-perf`
  (`tests/conftest.py`, `pytest.ini`, `Makefile`).

## 2. Parallel tests

- [ ] 2.1 PD-8: `pytest-xdist`, `make test -n auto`; fix the tests that share state. Gate: two
  `make test` runs green.

## 3. Formatting gate

- [ ] 3.1 PD-4: `make format-check` in `check-quality`; format the tree in its own commit.

## 4. Testkit

- [ ] 4.1 PD-5, test first: `probe_timeout` on `wait_until` and `wait_until_async`
  (`rdf_persistence/testkit/bootstrap.py`, `tests/unit/test_testkit_bootstrap.py`); the docstring
  and `develop/testing.adoc` rule 11 mention it.

## 5. Docs checks and guide

- [ ] 5.1 PD-7, test first: the exported-helper check in `docs/tools/check_docs.py`.
- [ ] 5.2 PD-6: `howto/adopt.adoc` steps 4 to 7, then a fresh cold reader.

## 6. CI

- [ ] 6.1 PD-1: `make fuseki-image`, the fixture without `build=True`, the cache steps and the
  `develop` warm-up job in `.github/workflows/ci.yaml`. Proof on the PR's second CI run.

## 7. Close

- [ ] 7.1 Five review lenses, decisions in design.md, fixes; fresh checker; gates; PR; merge on
  green CI; archive.

## Roadmap

1.1 · 1.2 → 2.1 → 3.1 → 4.1 · 5.1 · 5.2 · 6.1 → 7.1
