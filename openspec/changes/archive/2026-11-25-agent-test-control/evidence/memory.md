# Memory measured (task 1.3), 2026-11-25

The lead's one-off runs, queued (`TEST_QUEUE_LABEL=measure uv run python -m tests.queue --
/usr/bin/time -v pytest <path> -n 0 --no-cov -p no:randomly -q`), on one process, at commit
`329074f4` plus the release toggled by `TEST_RELEASE`. All four runs exited 0 (every test passed).

| Run | Release | Maximum RSS | Wall time |
|---|---|---|---|
| `tests/feature -m "feature and not slow"` (99 tests) | off | 2,135 MB | 1:57.8 |
| same | **on** | **395 MB** (−82 %) | **1:09.7** (−41 %) |
| `tests/unit/api/test_allowed_actions_adversarial.py` | off | 2,083 MB | 1:34.9 |
| same | **on** | **239 MB** (−89 %) | **1:07.7** (−29 %) |

Targets of task 1.3 and the `@manual` scenarios of *A test worker releases memory between test
modules*: feature run under 600 MB — met (395 MB); no more than 10 % added wall time — met (the
runs got faster, not slower); the adversarial module no longer grows with its tests — met (239 MB
for the module, against about +35 MB per test before).

The "off" figures match the investigation's (1.97 GB for the feature run, inputs/memory.md).
