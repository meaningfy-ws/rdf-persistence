> Derives from: EPIC `test-lanes` (proposal.md, shaped 2026-11-09); design: design.md; answers in
> inputs/seed.md.

Two stages, **one PR per stage** into `develop`, each merged on green CI before the next starts.
The branch is cut from `develop`, not from a feature branch in flight. Within a task, tests come
first (the `T-n` of design.md). Per task: the affected test folders (from task 1.4 on:
`make test-changed`), `make check-quality`, `make clean-code`. Once per stage, before the PR:
`make check-all` and `make test-containers` (both stages touch the testkit). Every report names
each make target run, with its time and test count. Before each task the lead runs gitnexus impact
on the symbols it touches.

## 1. Stage 1: the developer lanes

- [x] 1.1 T-5, then the freshness guard in `rdf_persistence/testkit/freshness.py` (PD-7, DEC-8).
  Report the 2-test file's wall time with `-n 0` and `-n auto`, before and after.
  Satisfies: rp-generation "The freshness check runs once per parallel session".
- [x] 1.2 Register `slow` in `pytest.ini`; T-4 in `tests/unit/test_markers.py`. Profile
  (`uv run pytest tests/unit tests/feature -n auto -q -p no:randomly --durations=60 -o addopts=""`),
  confirm each candidate alone by PD-4's measure, and decorate each slow test. List the marked
  tests and their set-up + call times in the report. Satisfies: rp-developer-checks "The fast lane
  leaves out slow tests".
- [x] 1.3 Add `PROFILE_MARK`, `test-fast` and `profile-tests` to the `Makefile` (design § Make
  targets). Run both; report times and counts, and that `make test-unit` still runs the slow tests
  with the coverage floor. Satisfies: "The fast lane leaves out slow tests", "Check timings come
  from a repeatable profile" (command half).
- [x] 1.4 T-1, T-2, then `tests/changed.py` (rules, `Selection`, git listing, `-n` choice, `main`)
  and the `test-changed` target. Run it on this branch, on a clean checkout of `develop`, and for
  the Goals' three selections (one test file, `domain`, `services`); report the times against the
  Goals. Satisfies: "The tests of the changed files run on their own" (all six scenarios).
- [x] 1.5 Docs: `develop/agents.adoc` gates table (per task `make test-changed`; `test-fast` as the
  fallback; `PYTEST_N`, `BASE`), `develop/testing.adoc` (when and how to mark `slow`, PD-4),
  `develop/index.adoc` (the lanes; table rows for `test-fast`, the three `test-changed` selections
  and `check-all`, with dates; the slowest tests named), `questions.adoc` (the question "Which
  tests do I run while developing?"); the gate line in `AGENTS.md`; the `tests/conftest.py`
  docstring and the `pytest.ini` marker comment (test-kind markers by path; `slow` by decorator on
  the test). `make check-docs` passes. Satisfies: "Check timings come from a repeatable profile"
  (table half).
- [x] 1.6 Fold `test-profiling` in (DEC-1): a superseded note at the top of its `proposal.md`
  naming `test-lanes`; its row in `openspec/changes/README.md` marked superseded; its inputs and
  spec delta untouched. `openspec validate --all --strict` passes.
- [ ] 1.7 Stage gate: `make check-all`, `make test-containers`; review (lenses L1 to L3, L4+L5 one
  pass); PR into `develop`, merged on green CI.

## 2. Stage 2: a cheap toy set-up

- [ ] 2.1 Measure before: `uv run pytest tests/unit/entrypoints -n auto -q` wall time, three runs,
  idle machine. T-3, then `TokenSigner(key=...)` (DEC-7), the toy's per-process key and `World`'s
  signer in `tests/unit/entrypoints/test_library_app.py` (PD-6). Run the entrypoint, testkit and
  feature folders and `make test-fast`. Measure after, the same way. Satisfies: rp-testkit "A test
  signer can start from a given key"; DEC-6.
- [ ] 2.2 Adversarial tester on 2.1 (RISK-3): tests that build two signers or two `ToyService`s
  and compare tokens or keys; `rotate` after `key=`; a token from a plain `TokenSigner()` against
  the toy. Accepted findings go into design.md, then one fixer.
- [ ] 2.3 Timings: `develop/index.adoc` rows for the entrypoint folder before and after, the
  `services` selection of `make test-changed` against its Goal, and `check-all` re-measured; wherever the docs describe `TokenSigner`, mention `key=`.
- [ ] 2.4 Stage gate: `make check-all`, `make test-containers` (`tests/integration/api/` builds
  `ToyService`); review; PR into `develop`, merged on green CI; then archive the change
  (`/opsx:archive`).

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5 · [x] 1.6 · [ ] 1.7 · [ ] 2.1 · [ ] 2.2 · [ ] 2.3 · [ ] 2.4

## Verification

T-1 to T-5 in `make check-all`; each target run and timed in its task against the Goals in
design.md; `openspec validate --all --strict`; the clarity gate on design.md + tasks.md (≥ 9/10).
