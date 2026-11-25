# Redis claim_idle redelivery test (task 3.5, PD-14)

`tests/integration/adapters/test_redis_events.py::test_a_receiver_that_raised_gets_the_message_again_without_a_restart`
runs only under `make test-containers` (local; no CI lane runs containers).

- 2026-11-25, builder of task 3.5, on `f5cb6fbc` plus the task's edits, Docker available:
  `uv run pytest -q -p no:randomly tests/integration/adapters/test_redis_events.py -k without_a_restart`
  → 1 passed.
- Planted mutation `claim_idle_seconds=600`: the test failed (the receiver's second call never
  came within 5 s); reverted.
- The lead's `make test-containers` on the stage 3 branch before its PR: recorded in the stage 3
  PR body under Results.
