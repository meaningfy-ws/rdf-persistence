EPIC: aggregate-guards (proposal.md, #305, #309). Decisions: DEC-1 to DEC-7; design.md D-1 to D-8.

> Derives from: `proposal.md`. Review per stage: one pass (SMALL; P-0005 applies from MEDIUM).

## 1. A rule reads a referenced aggregate (#305), PR 1, branch `feat/reader-aggregate`

- [ ] 1.1 Tests first: T1 to T7b (`design.md#stage-1-305-the-reader-hands-over-an-aggregate`), in
  the files named there. RED: `_Reader` has no `aggregate`.
- [ ] 1.2 `GuardContext.removed` and `GuardContext.read_cache`, kept on the transaction
  ([D-2](design.md#d-2)). The reader's `decode` parameter and `_Reader.aggregate`
  ([D-1](design.md#d-1), [D-3](design.md#d-3)). `Conflict` passes `run_aggregate_validators`
  ([D-4](design.md#d-4)). Covers DEC-1 to DEC-3 and DEC-6. Accept: T1 to T7b, E1 to E9;
  `make test-fast check-quality` (port change).
- [ ] 1.3 `user-manual/access.adoc`: reading a referenced aggregate, the version dependence
  (RISK-1), the symmetric rule (RISK-3), and a remove after a read (RISK-5). Accept:
  `make check-docs`.
- [ ] 1.4 Lead: `make check-all`, `make test-containers` (T6 integration), one review pass, PR.
  This EPIC lands with it.

## 2. Delete rules (#309), PR 2, branch `feat/delete-validators`

- [ ] 2.1 Tests first: T8 to T17 (`design.md#stage-2-309-delete-rules`). RED: `ServiceKit` has no
  `delete_validators`.
- [ ] 2.2 `DeleteValidator`, `DeleteValidators` and `run_delete_validators` ([D-6](design.md#d-6)).
  The `WriteGuard.prepare_remove` port, its call in `Transaction.remove`, and `Recording`
  ([D-5](design.md#d-5)). `may_read` on `Aggregates.remove` and the route ([D-7](design.md#d-7)).
  The kit and `install_service` argument, and the top-level export of `DeleteValidator`. Covers
  DEC-4 and DEC-5. Accept: T8 to T17, E10 to E18; `make test-fast check-quality`.
- [ ] 2.3 Docs: `user-manual/access.adoc` (delete rules, cascades and RISK-2, the comment exemption
  [D-8](design.md#d-8)), `architecture/data-flows.adoc` (the remove path), and the question
  "How do I refuse a delete?" in `questions.adoc`. Run `make refresh-surface`. Accept:
  `make check-docs`.
- [ ] 2.4 Lead: `make check-all`, `make test-containers`, one review pass, PR.

## 3. Close

- [ ] 3.1 Scenario-map rows for the new tests (each stage adds its own).
- [ ] 3.2 After the last merge: reconcile the proposal, archive, and comment on #305 and #309.

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 1.4 · [ ] 2.1 · [ ] 2.2 · [ ] 2.3 · [ ] 2.4 · [ ] 3.1 · [ ] 3.2

## Verification

Each stage: its T-rows go red, then green; `make check-all` and `make test-containers` before each
PR; `openspec validate aggregate-guards --strict`; the PLAN gated (`evidence/clarity-gate.md`).
