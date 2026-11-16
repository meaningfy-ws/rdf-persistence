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

- `rp-developer-checks` (modified): the timeout, the quarantine marker, the mutation target,
  the Hypothesis profile.
- `rp-testkit` (modified): `shared_key()` and the `poll_seconds` of the waits.
