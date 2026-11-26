# Q&A: test-control-testkit (secondary; never groomed)

Three rounds, 2026-11-26, in one session with the owner. Read before the rounds: issue #403, the
archived `2026-11-25-agent-test-control` change (proposal, design D-1 to D-4), `tests/queue.py`,
`tests/changed.py`, `tests/testmon_data.py`, the Makefile's CI, `test-changed` and `test-seed`
blocks, `develop/testing.adoc#test-control`, `tests/unit/tooling/`. Rules loaded: R-0002 to R-0005.

Stated without a question and not contradicted (round 1's preamble): finding 1, print
`tests_plan.hints` before the fallback reasons; finding 2, `test-changed` runs `uv run --no-sync`;
finding 3, the seed cleanup runs inside the queued command; finding 4, under `CI` the worker count
silences stderr and `PARALLEL` falls back to `-n auto`, never `@workers`; each fix starts with a red
test in `tests/unit/tooling/`, the Makefile ones through `make -n` dry runs.

| # | Round | Question | Answer | Becomes |
|---|---|---|---|---|
| 1 | 1 | Fold OPEN-2 (move to the testkit) in? | Yes: fixes and testkit move | appetite, DEC-1 |
| 2 | 1 | Finding 6, the lock's scope | Fix the wording: the lock is per user | DEC-2 |
| 3 | 1 | Finding 5, a bad `PYTEST_CHANGED_N` | Usage error, exit 2, with a message | DEC-3 |
| 4 | 1 | Risk outside the work | MWB2's copy drifts until it adopts the testkit; accept, post the diff on MWB2 #129 | RISK-1 |
| 5 | 2 | What moves | All three; `changed.py` made configurable | DEC-4 |
| 6 | 2 | How a Makefile calls them | `python -m rdf_persistence.testkit.<module>`; the `tests/` copies are deleted, no shims, no console scripts | DEC-5 |
| 7 | 2 | Stability | Public testkit API under semver | DEC-6 |
| 8 | 2 | What the EPIC proves | All four: moved tests pass with only their imports changed; runs from the installed package; the full gates green after the move; an import-linter guard | scenarios, DEC-7 |
| 9 | 3 | How a repository configures the planner | A classifier callback: the repository keeps `classify(path)` and `is_testmon_visible(path)`, the testkit owns the rest | DEC-4 |
| 10 | 3 | The value types and the model guard | Generate them from `rp_testkit.yaml` | DEC-8 |
| 11 | 3 | Appetite and stages | LARGE, three stages, three PRs | appetite, DEC-9 |
| 12 | 3 | MWB2's adoption (D-12) | A comment on MWB2 #129 naming this change and its release | DEC-10 |

The change id became `test-control-testkit` (not `test-control-fixes`) once the move was in scope.
