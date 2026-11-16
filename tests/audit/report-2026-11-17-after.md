# Test suite: before and after the grooming, 2026-11-17

Change `test-suite-grooming` (openspec/changes/archive/…-test-suite-grooming once archived). The
*before* is the audit of 2026-11-16 (`report-2026-11-16.md`), taken before any grooming change;
the *after* is the final code of the change, measured alone on the same 20-core machine with the
same commands (run A through `make test` with `PYTEST_ADDOPTS`, the make targets as given).

## Headline

| Measure | Before | After | Change |
|---|---|---|---|
| Unit + feature test cases | 7,357 passed, 18 skipped | 6,790 passed, 0 skipped | −567 cases (−7.7 %); 639 merged or dropped, about 70 tests added by the change |
| Unit + feature test functions (map rows) | 3,439 | 3,460 | renamed, split and moved; new guards added |
| Container cases (`make test-containers`) | 267 | 257 | −10 (P-31, P-34, the e2e duplicate) |
| Perf lane (`make test-perf`) | 2 tests, not run in the audit | 10 tests, 20 s (needs Docker) | timing asserts moved here from the lanes |
| Run A wall (unit + feature, no coverage) | 123 s | 72 s | −41 % |
| `make test` (with coverage) | ≈ 214 s | 127 s | −41 % |
| `make check-all` | 3 min 59 s | 2 min 28 s | −38 % |
| `make test-fast` | 126-147 s (under load) | 55 s (alone) | |
| `make test-containers` | 311 s | 297 s | −4 % |
| Coverage of `make test` | 95.59 % | 95.60 % | unchanged |
| Domain mutants (`make mutation`, 1,085) | 974 killed, 94 survived, 17 untested | 974, 94, 17 — **the identical set** | no defect-detection lost |
| Asserts without a message (rule 11) | 1,301 | 0 | |
| Stage-named adversarial files (rule 21) | 6 | 0 | |
| Wrong `slow` markers | 27 (18 missing, 9 superfluous) | 0 at the 2 s / 0.5 s thresholds | 17 added, 1 removed, the rest now fast |
| Hung-test limit / CI job limit | none / none | 120 s (parallel lanes) / 30 min | |
| Test order | fixed | random (pytest-randomly), seed in the header | |
| Rule-1 guard for domain tests | none | an import-linter contract | |

## Where the time went

Summed per-test time is about the same (before 442 s set-up + 524 s call; after 420 s + 579 s):
the cases removed were cheap ones. The 41 % wall-time gain comes from cutting the long tail that
held the last workers busy and from distribution:

- `bootstrapped` (2.5 s per test, 26 tests) became a session template: `test_lock_step.py` alone
  93 s → about 50 s.
- The 44 read-only listing tests share one service: about 25-30 s of set-up → 1.35 s.
- `shared_key()` and fast polling of in-process fakes removed about 9 s of fixed waits.
- `--dist loadgroup` and the removal of the 2-6 s set-ups shortened the tail of the parallel run.
- Two proposals (a shared schema view, shared book triples) were built, measured at no saving and
  not landed.

Costliest fixtures after (summed set-up, xdist): `service` 85.7 s (341 tests), `scene` 75.9 s,
`world` 58.0 s, `generated_toy` 49.6 s, `bootstrapped_template` 39.8 s (built once per worker),
`books` 14.3 s. A profile of `ToyService()` is under the change's *Debt*.

## What a test now guarantees that it did not before

- Every merge of parametrised cases kept the case that fails under its branch's mutation; three
  weaker survivors were caught by review and restored.
- Three guards a stage had lost were restored and proven by a regression that makes them fail:
  the JSON-LD non-inline context refusal (back in the unit lane, under `no_network`), the
  N-Quads import half, the 413 order proof (spies instead of a clock).
- Problem responses are asserted by status and `type`; RDF by isomorphism with a printed diff.
- Every feature scenario names its spec scenario; the scaffold's example feature is gone.
- Every test function maps to a spec scenario, requirement or capability
  (`scenario-map.csv`, kept in step by `make refresh-map`).

## Commands

```
PYTHONPATH=<skill>/scripts PYTEST_ADDOPTS="-p phase_times --phase-times-out=<out>/phases.jsonl --no-cov" make test
make check-all ; make check-generated ; make test-containers ; make test-perf ; make mutation ; make test-fast
```

All exit 0 on the final commit of the change.
