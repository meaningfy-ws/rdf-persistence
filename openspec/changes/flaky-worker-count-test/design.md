# Design: flaky-worker-count-test

> Derives from: EPIC `flaky-worker-count-test` (proposal.md, DEC-1). Issue #432.

## Context

`Makefile`: `PYTEST_N ?= $(shell uv run --no-sync python -m rdf_persistence.testkit.run_queue
--workers 2>/dev/null)` (recursive, re-evaluated at each expansion) and `PARALLEL = -n $(or
$(PYTEST_N),$(if $(CI),auto,@workers)) --dist loadgroup`. The test helper `make_prints(text,
**env)` runs `make --eval 'pn:;@echo "<text>"' pn` in an environment without the three knobs plus
`env`.

## Decisions

- **PD-1 The assertion.** `printed = make_prints("$(PYTEST)|$(PARALLEL)", CI="1")`; split on `|`;
  assert the command is `PLAIN_PYTEST`; match `PARALLEL` against `^-n (\d+) --dist loadgroup$`
  (a message naming the printed value when it does not match: `auto` or `@workers` would mean make
  did not count); assert `1 <= count <= workers(os.cpu_count(), None, 1)`. One expansion of
  `PYTEST_N`, so no race with the memory reading.

## Test plan

| TC | Scenario | Proof | Tier |
|---|---|---|---|
| TC-1 | the count is read once | the rewritten test passes; it can no longer fail on two different counts, since it reads one | unit (`tests/unit/tooling/`) |
| TC-2 | it still fails when make does not count | with `PYTEST_N` absent on CI the value is an integer; a mutation that prints `auto` (e.g. running with `PYTEST_N=` set empty) makes the regex assertion fail (checked by hand once, reported) | unit |

## Delivery decisions

- **D-1 Review (one pass L2+L3, PR #436): no Critical; two under the floor.** S1: the bounds
  assert covers both ends in one line (as before the change). S2: the TC-2 probe is recorded, not
  a test (as planned).

## Risks

- **RISK-1 the test proves less.** It no longer compares `PYTEST_N` with `PARALLEL`; both come
  from one variable by construction (`PARALLEL` contains `$(PYTEST_N)`), so the comparison proved
  nothing beyond the integer check. Accepted.
