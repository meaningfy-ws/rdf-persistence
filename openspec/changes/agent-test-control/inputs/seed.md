# Seed: agent sessions spend their time waiting for tests (secondary, never groomed)

Source: the owner's question of 2026-11-25 ("why does rdf-persistence development still take so
long, now that skillery is lighter?"), answered from the Langfuse traces of the latest skillery
release (traces tagged `skillery:3.22.0`, from 2026-11-22; the installed release is 3.24.0, the
tag lags) and from this repository.

## What the traces showed (2026-11-22 to 2026-11-25, rdf-persistence sessions)

| Session | Bash wall time | Subagent LLM time |
|---|---|---|
| d3fc332a (grant-roles, two builders) | 5.4 h | 0.3 h |
| c98d2bc7 | 3.9 h | 3.1 h |
| 5918bdd4 | 3.2 h | 0.7 h |
| 8756b290 | 1.5 h | 0.3 h |

- Skill and tool overhead is negligible (a Skill call about 50 ms, Read about 25 ms).
- In d3fc332a both builders spent about 2.5 h in repeated 10-minute waits on their gate logs,
  `timeout 590 tail --pid=<pid> -f /dev/null` and `timeout 590 tail -f <log> | grep -m1 ...`:
  polling that the `no-poll-loops` hook does not catch.
- The gates failed for reasons of contention, not code: `Timeout (>120s)`, a venv broken by a
  concurrent `uv sync` ("Restore venv and rerun failing areas"), lock-step and freshness tests
  failing while another process regenerated. Each failure cost another 10-minute rerun.
- Four to five rdf-persistence sessions started together (11:05 and 14:28 on 2026-11-25), each
  with builders; load average 23 to 50 on 20 cores. One `make check-all` took about 38 min
  against 13 in the durations table.

## What the repository showed

- `Makefile:54` `PARALLEL = -n auto --dist loadgroup`: every lane starts 20 workers; the
  `-n 4` the owner remembered was only in builders' hand-typed narrow runs.
- `make test-changed` falls back to `make test-fast` (exit 3 of `tests/changed.py`) on any change
  in `core`, `rdf_persistence/model/`, a `tests/*.py` helper, `tests/fixtures/` or a shared file.
  Eight of the last nine merged feature PRs (#355 to #388) hit the fallback; so does the current
  `change/review-floors-s1`. The builders' "narrow" gate is the full fast suite.

## Selection approaches measured on PR #388 (one function, `_string` in `core/domain/sparql.py`)

| Approach | Test files selected | Blind to fixtures | Cost per check |
|---|---|---|---|
| `test-changed` today | 264 / 264 (fallback) | n/a | none |
| grimp import graph (installed with import-linter) | 198 / 267 | yes | 0.03 s |
| GitNexus call graph, depth ≤ 5 | 65 / 264 (includes `test_sparql.py`) | yes | reindex, about 5 min |
| GitNexus, depth 7 | query ran out of memory | yes | |
| ast-grep / Serena | about grimp / about GitNexus, slower | yes | |
| pytest-testmon 2.4.0 | the tests that executed the changed lines | no | one seed run per worktree |

testmon facts (testmon.org, PyPI, read 2026-11-25): xdist supported since 1.4; non-Python files
(YAML, `.feature`, templates) not tracked; under coverage it records nothing
(`--testmon-nocollect` forced); first run must be a full run; database `.testmondata` in the
rootdir (`TESTMON_DATAFILE` moves it); sharing the file across machines is discouraged.
