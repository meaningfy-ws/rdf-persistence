# Selection checked (task 2.5, RISK-1), 2026-11-25

In a separate worktree (`.worktrees/atc-2.5`, branch `atc/task-2.5` off `change/agent-test-control`
at `04c190e3`), removed afterwards.

**Seed.** `make test-seed`: 10,235 tests (2 failed, 10,228 passed, 5 xfailed) in 6 min 5 s of
pytest on 17 workers (`test queue: 17 workers (20 cores, 45645 MB available)`), 7 min 39 s in
total with 1 min 33 s queued; the data was swapped in (`.testmondata`, 9.5 MB). The two failures:
`test_log_calls` (the testkit logger, fixed by the lead, `f7139f0b`, `9cacfd74`) and
`test_a_step_too_long_for_the_parser_is_refused_with_its_own_message` (pre-existing, order
dependent: it relies on rdflib exhausting the recursion limit at about a hundred patterns, which a
Hypothesis run raises meanwhile; it passes alone and in its module; under the floor).

**A defect the replay found.** The first replay planned without data: `check` compared the full
package versions with testmon's stored string, which drops patch versions, and reported
`packages changed since the seed` right after the seed. Fixed by the lead (`fa155a7c`,
`drop_patch_version`); `check` then reported the seed sound.

**Replay.** PR #388's change to `_string` in `rdf_persistence/core/domain/sparql.py` reverted as
an uncommitted change, `make test-changed BASE=HEAD`, twice:

| Run | Selected | Result | Wall time |
|---|---|---|---|
| 1 | 3,720 tests (36 % of the seed's 10,235); no fallback | 8 failed, 3,710 passed, 2 xfailed | 7 min 32 s |
| 2 | the same 3,720 | the same 8 failed | 6 min 38 s |

- The 7 `tests/unit/core/test_sparql.py` tests that guard #388 failed in both runs: the
  regression is caught.
- The 8th is the seed's recorded failure (`test_log_calls`, unfixed in that worktree): testmon
  keeps selecting a failure the seed recorded.
- The same selection on both runs: the read-only selection (`--testmon-nocollect`) holds.
- xdist ran with `--dist loadgroup` on 4 workers (`PYTEST_CHANGED_N` default), unqueued.
- Today, without selection data, the same change falls back to the full fast lane (exit 75).

**Trade-off seen.** `_string` sits under every SPARQL write, so its selection is a third of the
suite; on 4 unqueued workers that took longer than the fast lane does on 17 queued workers on an
idle machine (≈ 4 min), while using a quarter of the cores and never waiting in the queue. A
change in a leaf module selects far fewer. `PYTEST_CHANGED_N` raises the worker count when the
machine is free. Measured against DEC-8 after the merge (task 4.3).
