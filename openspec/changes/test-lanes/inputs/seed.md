<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: test lanes

## Seed text (developer, 2026-11-09)

> can you think on how to partition and split the tests, so that during the development only the
> relevant tests are executed, and only at the end the whole suite. otherwise it takes forever to
> run all tests and do a check all

Then: "please shape an epic describing these concepts, and plan it".

## Intake findings (lead, 2026-11-09)

Read: `Makefile` (lanes `test`, `test-unit`, `test-feature`, `test-containers`, `test-perf`,
`UNIT_LANE`, `COV_FLAGS`), `pytest.ini`, `tests/conftest.py` (path-based markers),
`tests/unit/entrypoints/conftest.py`, `tests/toy_service.py`, `rdf_persistence/testkit/tokens.py`,
`openspec/specs/rp-developer-checks/spec.md`, the candidate change `test-profiling` (its proposal,
seed and spec delta), `develop/index.adoc` ("How long the checks take"), `develop/agents.adoc`
(the gates).

Measured on the developer laptop (12 cores), branch `feature/mwb2-files-stage-1`, without coverage:

```
uv run pytest tests/unit tests/feature -n auto -q -p no:randomly --durations=40 -o addopts=""
3682 passed, 18 skipped in 405.47s   real 6m52s  user 27m09s  sys 1m42s
```

The machine is saturated for the whole run. The time goes to two kinds of test:

1. **Tests that shell out or run whole tools** (mypy, tsc, a wheel build, `rp-generate`, pytester
   sessions): `test_packaging.py::test_a_consumers_type_checker_reads_our_annotations` 62 s;
   `generation/test_freshness.py` 12 to 32 s per test; `test_ext_pydantic_split.py`,
   `test_ext_shacl.py`, `test_shapes.py`, `test_stage3_adversarial.py`, `test_boundary_check.py`,
   `test_placement.py`, `test_transform.py`, `testkit/test_adopt_step6.py`,
   `testkit/test_stage1_adversarial.py` 10 to 35 s each. Full list: `temp/durations.txt` (not kept).
2. **Entrypoint tests set up a new `ToyService` per test** (function-scoped `service` fixture,
   `tests/unit/entrypoints/conftest.py:19`): ~10 to 12 s of set-up each under load, on hundreds
   of tests.

One `ToyService()` on an idle machine: first 1.11 s, second 0.59 s. cProfile of one construction
(1.37 s with profiler overhead): `rsa.generate_private_key` 0.50 s (in `TokenSigner.rotate`, called
by `TokenSigner.__init__`), `schema_structure.iri_types` 0.39 s, `documents.__init__` (Turtle parse)
0.30 s. A fresh 2048-bit RSA key per test is the largest single cost.

## Questions and answers (2026-11-09)

1. **Overlap with the candidate `test-profiling`?** Recommended: fold it in. **Answer: fold it in.**
   This EPIC takes over its requirement (a repeatable profile command, the timings table); its
   proposal and the changes README are marked superseded; its inputs stay.
2. **Scope: also speed up the suite (the entrypoint app fixture), or only split lanes?**
   Recommended: include, as the last stage. **Answer: include, last stage.**
3. **How is a test marked `slow`?** Recommended: a file table in `tests/conftest.py`.
   **Answer: per-test decorator (`@pytest.mark.slow`).**
4. **Gates?** Recommended: inner loop and per task `make test-changed` (matched folders, their slow
   tests included) + `check-quality` + `clean-code`; `make test-fast` when unsure; `check-all` +
   `test-containers` once before the PR. **Answer: as recommended.**

## Lead's choices while planning (the developer may overrule)

- The intake profile shows the fixture cost is the RSA key, not the app. Stage 2 therefore reuses
  the signing key per worker process and keeps a fresh app per test, rather than sharing one app
  across a module with a store reset (the option discussed before shaping). Same speed-up, no
  state shared between tests. Recorded as DEC-6.
- From `test-profiling`'s accepted answers: profile without coverage; name the top 15; report
  set-up and call separately (`--durations` does).

## Test scenarios the EPIC must prove

- `make test-changed` after editing one file in `rdf_persistence/services/` runs only
  `tests/unit/services/` (slow tests there included) and no other folder.
- A changed test file runs itself; a changed `tests/integration/` file is named as needing
  `make test-containers`, and not run.
- A change to a shared file (`tests/conftest.py`, `pytest.ini`, `pyproject.toml`, `uv.lock`,
  `Makefile`, `tests/toy*.py`) or an unmapped file runs `make test-fast` instead.
- No change against `develop` runs nothing and says so.
- `make test-fast` runs every unit and feature test not marked `slow`, without coverage.
- `make check-all` and CI still run every test, slow ones included, with the coverage floors.
- `make profile-tests` prints the 15 slowest tests, set-up and call apart.
- Two `ToyService`s in one worker sign with the same key; a test that needs another key still gets
  one (`rotate`, or its own `TokenSigner`).
- The entrypoint folder's wall time drops (measured, recorded in the timings table).

## Risks raised

- A slow test breaks and nobody sees it until the stage gate.
- The mapper misses a cross-layer break (a services change breaking entrypoint tests).
- A shared key hides a test that relied on distinct keys.
- `-n auto` start-up costs more than a small selection's run.
- Someone forgets the `slow` decorator on a new slow test.

## Plan review (2026-11-09)

An independent attack and clarity-gate pass scored the first PLAN draft 7/10 and found ten defects
(the per-worker freshness check was the largest: ≈ 4 s per xdist worker, so a 2-test file took
22.1 s with `-n auto` against 7.3 s with `-n 0`). The lead folded every finding into design.md
(§ Plan review) and added DEC-8 (the freshness check once per session) to the EPIC. Measured
then: `tests/unit/domain/` 5.8 s with `-n 0`, 12.6 s with `-n 4`; `tests/unit/services/` 32.9 s
with `-n auto`.
