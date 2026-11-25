# Hand-over: agent-test-control, after stage 1

## Done
Stage 1 (the only stage): every build task, 1.1 to 3.3; PR into `develop` (merged by the
watch-and-merge command after this note). Evidence: `evidence/memory.md`, `evidence/selection.md`,
`evidence/clarity-gate.md`; proposal.md *Delivered*.

## Decided since the PLAN
D-1 to D-4 (design.md, Delivery decisions); DEC-10 (proposal.md), the developer's, during delivery.

## Open
- The skillery issue is meaningfy-ws/skillery#360; task 4.1 still owes it a comment with the
  merged file list and the measured times.
- Follow-ups outside this EPIC (D-3): build the `Annotated[…, Depends(kit.gate.caller)]` once per
  class, not per kit; load each schema once per process; report the `SchemaView` per-instance
  `lru_cache` to linkml-runtime. Other repositories adopting the queue or the testkit plugin
  (DEC-1, DEC-10).
- Under the floor: `test_a_step_too_long_for_the_parser_is_refused_with_its_own_message` depends
  on test order (rdflib's recursion limit, raised by Hypothesis meanwhile); pre-existing.
- After the merge: every worktree in use runs `uv sync` (the new pin), and its lead runs
  `make test-seed` once.

## Next
Task 4.3 (DEC-8, Langfuse, the first epic session with three sessions running), then 4.1 and 4.4.
Read first: `tasks.md` §4, proposal.md DEC-8.

## Prompt
Act as the team lead. Close openspec/changes/agent-test-control from handover.md: measure DEC-8
(task 4.3), file the skillery issue once approved (4.1), then archive (4.4).
