# #403-3 reproduced live (stage 1, 2026-11-26)

In `.worktrees/tct-s1`, the lead started `make test-seed` with the **old** recipe, which runs
`rm` and then the queued pytest, with the swap outside the queue. While it ran, the stage's
**new** recipe (`tests.testmon_data seed` inside the queue) was started as a second
`make test-seed` in the same worktree.

- First seed: pytest `10262 passed, 5 xfailed` in 384 s. Its swap then printed
  `no .testmondata.seed to swap in` and exited 70.
- Second seed: it took the queue as soon as the first seed's pytest exited, and its clean
  deleted the first seed's file before that seed's swap ran (`test queue: waited 499s`).

This is the race of #403-3. With the new recipe the swap runs inside the queued process, so a
second seed cannot start before it ends (PD-7).
