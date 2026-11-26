# Seed spike (test-memory-followups, task 2.1, PD-6)

Verdict: FAIL. The combined run (c) cannot run: testmon 2.4.0 refuses to run together with pytest-cov
while branch coverage is on (`.coveragerc` sets `branch = True`).

Worktree `.worktrees/tmf-spike` at 5fc356de4529d2700fa06f3863a1a05d9cda9521, synced with all extras by
the lead before the runs reported here (an earlier (a) run was discarded and redone after the sync).
Python 3.13.11, pytest-testmon 2.4.0, pytest-cov 7.1.0, coverage 7.17.0, pytest-xdist 3.8.0.
Folders: unit `tests/unit/schema/` (157 tests), feature `tests/feature/test_incoming_events.py` (1 test).
Every run: through `uv run python -m rdf_persistence.testkit.run_queue -- bash spike.sh <stage>`
(`UV_NO_SYNC=1`, `TEST_QUEUE_LABEL=spike-<a|b|c>`), `-n 4 --dist loadgroup`, own `TESTMON_DATAFILE`,
no swap. Times are measured inside the queue hold (the queue wait of up to 796 s is excluded).
Scripts: spike.sh, drive-a.sh, drive-bc.sh in this folder. The lane coverage floor is set to 0
(narrowed folders); all else as the Makefile lanes.

## Runs
(a) coverage only, two lanes, two queue holds, random order:
- unit: `pytest tests/unit/schema <UNIT_LANE ignores + tests/generator> -n 4 --dist loadgroup -m "unit and not quarantine" --cov=rdf_persistence --cov-report=xml:... --cov-fail-under=0 --junitxml=...`
  157 passed, 11.03 s (pytest itself 5.82 s); coverage total 24 %.
- feature: same with the file `tests/feature/test_incoming_events.py`, `-m "feature and not quarantine"`;
  1 passed, 10.12 s; coverage total 54 %.
  Sum (a): 21.16 s.
(b) selection only, one hold: `pytest tests/unit/schema tests/feature/test_incoming_events.py <ignores>
  -m "(unit or feature) and not quarantine" --testmon --testmon-forceselect -n 4 --dist loadgroup -p no:randomly`,
  `TESTMON_DATAFILE=.testmondata.a`: 158 passed, 9.88 s.
(c) the mechanism, one hold, `TESTMON_DATAFILE=.testmondata.b`, the two lane commands of (a) plus
  `--testmon --testmon-forceselect -p no:randomly`, in order: both lanes aborted, exit 3, 12.51 s.
  Every worker raised an INTERNALERROR (run-c.log lines 17 to 357 and 377 to 513):

    testmon.testmon_core.TestmonException: testmon doesn't support simultaneous run with
    pytest-cov when branch coverage is on. Please disable branch coverage.
    (testmon/testmon_core.py:701, setup_coverage, called from start_testmon)

## Criteria
1. Coverage of (c) equals (a): not measurable, (c) recorded none. Fail.
2. Sample changes (domain, services, test file) selected by (b) versus (c): not run; (c) produced no
   usable data (it recorded nothing past the abort). Fail.
3. Wall time of (c) at most 15 % above (a): not meaningful, (c) did not complete. Fail.
Any tracer warning: none printed; the plugins conflict with an error, not a warning.

## Why this is a verdict and not a retry
The only way past the error is to turn branch coverage off (`--cov-branch` is off or `branch = False`),
which changes the coverage numbers and the coverage floors: that is the "coverage differs" fail of
PD-6 and a design change, not a spike detail. Not tried (P-0019).

## Departures
- Floors set to 0 on the narrowed folders (otherwise 24 % and 54 % fail the 80 % and 50 % floors).
- XML and junit reports went to the scratch folder, not the worktree root.
- The sample-change measurement would have used the testmon invocation of `tests.changed` narrowed to
  the two folders (`make test-changed` plans tests/unit, tests/feature and tests/generator, and any test
  absent from a narrowed data file counts as new and runs, so the full suite would run). Not reached.

## Upstream finding (external)
pytest-testmon 2.4.0 raises TestmonException when pytest-cov runs with branch coverage:
reproduce with `pytest tests/unit/schema --cov=rdf_persistence --testmon` in this repository
(`.coveragerc` `branch = True`). The only option is to disable branch coverage.
