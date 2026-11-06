<!-- Parents: docs/modules/ROOT/pages/develop/index.adoc ("How long the checks take");
     docs/modules/ROOT/pages/questions.adoc ("What could strengthen it in the future").
     Seeds: inputs/seed.md. -->

# EPIC: Profile the slowest tests and checks

> Candidate EPIC, shaped 2026-11-06 from the v1 future list. Not planned: the PLAN (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.

**Golden-thread parent:** the timings table "How long the checks take" in
`docs/modules/ROOT/pages/develop/index.adoc`, which says "Detailed profiling comes later".

## Appetite

**TINY.** One concern in one place: measure where the time goes and record it in the existing
timings table. No new concept, no new tool unless the measurement needs it.

## Why

`make check-all` takes about 5.5 min, 4.5 to 5.5 min of it in pytest (2733 tests), and
`make test-containers` takes 2 to 3.5 min. The table in `develop/index.adoc` records these as rough
laptop wall-clock times, "not from profiling". The `test` target in the `Makefile` runs pytest with
coverage and no duration report, so nobody knows which tests or checks dominate.

## Solution outline

A profile names the slowest tests and the slowest check steps, and the timings table in
`develop/index.adoc` carries the measured numbers, with the date and commit of the run. The profile
is repeatable by a documented command, so the table can be refreshed. Whether the findings lead to
speed-ups is outside this EPIC: they become their own changes.

## Key decisions

- **DEC-1**: The timings table stays in `docs/modules/ROOT/pages/develop/index.adoc` and keeps its
  columns (Target, Tests, Time, Measured, Notes). Source: the task brief of 2026-11-06 and the
  table itself. Rejected: a separate profiling page.
- **DEC-2**: Checks run through `make` and Python tooling through uv. Source: `AGENTS.md`, Working
  conventions. Rejected: hand-rolled pytest pipelines as the documented way.

## Rabbit-holes

- Optimising while measuring. The EPIC measures; any fix is a separate change.
- Laptop noise. One run on one machine is a sample, not a benchmark; record the machine class and
  the run count.
- Coverage overhead. Profiling with and without `--cov` gives different answers; say which one the
  table shows.

## No-gos

- Speeding up any test, fixture or check.
- Parallel test execution (for example `pytest-xdist`) or changing the coverage floor.
- A CI performance dashboard or trend tracking.
- New runtime dependencies of the package.

---

## What Changes

- `docs/modules/ROOT/pages/develop/index.adoc`: the timings table filled from a profile, with the
  slowest tests and check steps named.
- Possibly a `make` target or documented command that produces the profile (open question Q-2).

## Capabilities

### New Capabilities

- `rp-developer-checks`: how long the developer checks take, measured and documented.

### Modified Capabilities

None.

## Impact

- Documentation only, unless a profiling target is added to the `Makefile`.
- No change to the package, its API or its dependencies.
