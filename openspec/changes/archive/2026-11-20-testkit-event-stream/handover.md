# Hand-over: testkit-event-stream, after stage 1 (the only stage)

## Done
Stage 1 is PR #213 into `develop`, covering tasks 1.1 to 3.2. The developer merges it after this
note.
- **What it adds:** `rdf_persistence.testkit.open_event_stream` and the generated `OpenedStream` and
  `StreamEvent`. The toolkit's lifespan now sets the flag `app.state.rp_lifespan_started`. The
  toolkit's own SSE tests run on the helper, and `Follow`, `follow`, `Block` and `parsed` are
  deleted. The how-to is `user-manual/test.adoc#event-stream`.
- **Review:** one L2+L3 pass, 10 findings, none Critical. W1 was re-labelled Critical and fixed as
  D-8. The rest are under the floor.
- **Gates:** both full-gates runs passed (PR body).
- **Acceptance:** accepted by the developer (`evidence/acceptance.md`). No docs owed
  (`evidence/docs-owed.md`). Archived in this PR.

## Decided since the PLAN
D-1 to D-8 (design.md, Delivery decisions).

## Open
- **#214:** `EventHub` has no public read that tells a follower is subscribed. A consumer cannot
  wait for the subscription before a commit without private state. The issue also covers the how-to
  outcomes from W3.
- **#215:** test hardening from the review (W2, W5, S1 to S5).
- **RISK-1:** `test-debt-paydown` can start once #213 is merged. Its PLAN still names `Follow` and
  needs the update RISK-1 describes:
  - its 1.4 shrinks to `test_relay.py`;
  - its PD-8 moves only `listening`, `mount`, `replace`, `reshape_grants`, `with_carol`,
    `another_book`, `events_of`, `opening` and `drained`;
  - it may take S1 to S3 from #215.
- **Consumer:** MWB2's deferred positive events-route test (v2-01 task 6.1) can proceed once a
  release holds this change.
- **Environment, for briefs:**
  - Builders must use absolute worktree paths with Serena. One builder's first edits landed in the
    main checkout.
  - A `make generate` that is killed leaves `.rp-generate-*` under `tests/fixtures/library`, which
    fails `test_boundary_check`: delete it.
  - Exporting a testkit name makes `check-docs` fail until `make docs-reference` runs.
  - `rdf_persistence/` must not contain the substring `EVENT_STREAM` (`test_packaging.py`).

## Next
None: the EPIC is delivered and archived. Before `test-debt-paydown` starts, update its PLAN per
RISK-1 above.

## Prompt
None for this change. For the next one: act as the team lead and deliver
openspec/changes/test-debt-paydown, after updating its PLAN per the RISK-1 note in
openspec/changes/archive/2026-11-20-testkit-event-stream/handover.md.
