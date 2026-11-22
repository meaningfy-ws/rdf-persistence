# Acceptance: refresh-map-collect

2026-11-22, retrospective. PR #294 delivered the fix and merged it on green CI (P-0013). The spine
was written afterwards at the developer's request. What stands in for a demo:
- TC-1 passes under the repository's real `pytest.ini`.
- On develop after the merge, `make refresh-map` printed `New ids with no row (0)` and exited 0.
- No clarity gate was run: the PLAN records work already delivered.
- No spec delta: no `rp-*` capability covers the refresher (proposal.md, Capabilities).
