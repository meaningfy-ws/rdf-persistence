<!-- Parents: the test-suite-care audit tests/audit/report-2026-11-16.md and its map
     tests/audit/scenario-map.csv; the owner's decisions of 2026-11-16 ("I accept everything"). -->

# EPIC: Groom the test suite: cheaper set-up, fewer redundant cases, the checklist kept

**Golden-thread parent:** the audit `tests/audit/report-2026-11-16.md` (proposals P-1 to P-8,
P-20 to P-34, P-40 to P-51, the library verdicts and the broken-rules tables) and the owner's
decisions recorded in its *Decisions* table.

## Appetite

**LARGE.** Five stages, one pull request each: set-up and libraries; merged cases; dropped
tests; broken checklist rules; assert messages (rule 11).

## Why

The suite (7,357 unit and feature cases, 267 container cases) is strong: mutation testing kills
about 92 % of `domain/`'s meaningful mutants. But half of the unit time is set-up, about 756
parametrised cases repeat one equivalence class, 14 tests repeat others or run nothing, the
`slow` markers are wrong in 27 places, CI has no timeout, Hypothesis is derandomised only on
some workers, and the testing checklist is broken in 14 of its rules.

## Solution outline

1. **Stage 1, set-up and libraries (class 1, no test removed):** P-1 to P-8 of the report;
   adopt `pytest-timeout`, a `quarantine` marker and an on-demand `make mutation` (mutmut);
   move the Hypothesis CI profile to `tests/conftest.py`; trial `pytest-randomly` once; drop
   `polyfactory`.
2. **Stage 2, merged cases (class 2):** P-20 to P-34, each keeping its named survivor case.
3. **Stage 3, dropped tests (class 3):** P-40 to P-45 and P-49 to P-51.
4. **Stage 4, broken rules except 11:** rules 1, 3, 5, 6, 7, 9, 10, 12, 13, 14, 15, 17 and 21
   as the report's tables list them.
5. **Stage 5, rule 11:** one message per assert, mechanically, in its own pull request.

## Key decisions

- **DEC-1**: Every report proposal is approved, class 3 included without the owner's sample
  check. Source: owner, 2026-11-16 ("I accept everything").
- **DEC-2**: Rule 11 lands last, in its own pull request. Source: owner, 2026-11-16.
- **DEC-3**: The lead commits, pushes and merges each stage on green CI. Source: owner's grant
  for this EPIC, 2026-11-16.
- **DEC-4**: `polyfactory` is dropped; rule 6's intent is met by the validated named builders of
  `tests/toy.py`. Source: report, *Libraries*.
- **DEC-5**: The `rp-messages` "empty commit spends a Served" question stays open; no test or
  code it touches changes in this EPIC.

## Rabbit-holes

- Refactoring production code to make a test cheaper beyond P-2's one signature change.
- Raising the mutation score: the 35 logic survivors are listed, not fixed, here.
- Rewriting the adversarial files: stage 4 renames them (rule 21) and fixes listed breaks only.

## No-gos

- No drop beyond the approved class 3 list; no W-7 drop.
- No change to production behaviour. Allowed API additions only: `ServiceKit` /
  `install_service` accept a `SchemaView` (P-2); the testkit gains `shared_key()` and
  `wait_until*(poll_seconds=…)` (P-5, P-8). `testkit.roundtrip.assert_isomorphic` already exists.
- No new test library beyond `pytest-timeout` and `mutmut`.

## Capabilities

- `rp-developer-checks` (modified): the timeout (parallel lanes), the quarantine marker, the
  mutation target, the Hypothesis profile.
- `rp-testkit` (modified): `shared_key()`, the `poll_seconds` of the waits, and
  `assert_isomorphic` as a public name.

## Reconciliation (as delivered)

Delivered as one pull request (PR_NUMBER) with each stage as a commit group (design.md D-1).

| Shape item | Final state | Where |
|---|---|---|
| Stage 1, P-1 (`bootstrapped` template) | delivered; `test_lock_step.py` alone 93 s → ~50 s | eb75194 |
| Stage 1, P-2 (shared schema view) | built, measured no saving, **not landed** | design.md PD-2 |
| Stage 1, P-3 (shared read-only listing) | delivered; 44 tests' set-up ~25-30 s → 1.35 s | 446c6a9 |
| Stage 1, P-4 (shared book triples) | built, measured no saving, **not landed** | design.md PD-4 |
| Stage 1, P-5 (`shared_key()`) | delivered; 6.05 s → 4.09 s on its two files | 3973823 |
| Stage 1, P-6 (slow markers) | delivered, re-timed alone after the merges (17 added, 1 removed) | d4ab453 |
| Stage 1, P-7 (dist mode) | delivered: `loadgroup` | da1876e |
| Stage 1, P-8 (`poll_seconds`) | delivered; 25.9 s → 20.2 s on five files | 6cfe4ab |
| Stage 1, libraries | pytest-timeout, quarantine marker, Hypothesis profile, `make mutation`, polyfactory dropped, **pytest-randomly adopted** | 0f0e1c6, 09570eb |
| Stage 2, P-20 to P-34 | delivered: 639 cases merged, survivors chosen by mutation (D-3); P-31's unit half under Debt | 5195044, 32f8dab, 36eae7c, 36c0781, 6260687, 5123a37, 4ad11f3 |
| Stage 3, P-40 to P-45, P-49 to P-51 | delivered: 10 tests dropped; two P-51 pins kept (D-4) | c8e58e7, 7c68159 |
| Stage 4, rules 1, 3, 5-7, 9, 10, 12-15, 17, 21 | delivered; rule-5 and rule-12 items with no fake or clock under Debt | 88d5688, e990aa7, fddd20a, a281aad |
| Stage 4, review fixes F-1 to F-8 | delivered | 1c96c27 |
| Stage 5, rule 11 | delivered: 1,301 asserts given a message; 0 left | 8d80a72, 99b4497, 5d89fd3 |
| Close | the full review's fixes (three restored guards, the rule-1 contract), the after report (6,790 cases, run A 72 s, `check-all` 2 min 28 s, identical mutation set) | 084db9f, 9057edf, 8aed6ed |

**Differences from the shape, with the reason:**

- **No-gos, "no new test library beyond pytest-timeout and mutmut":** `pytest-randomly` was
  adopted. PD-9 planned its trial and the adopt-on-green branch, which contradicted this no-go;
  the trial ran green on two seeds.
- **No-gos, allowed API additions:** the testkit also exports `assert_isomorphic` (finding F-8:
  a consumer test may use only public names). `ServiceKit`/`install_service` do NOT accept a
  `SchemaView`: P-2 was not landed.
- **DEC-2 and DEC-3:** one pull request, not five (D-1; the owner asked for local-first work,
  then for the whole change to be completed while away).
- **The perf lane needs Docker** (D-5), a cost the shape did not foresee.
- **Spec deltas:** the timeout requirement is narrowed to the parallel lanes (F-5).
