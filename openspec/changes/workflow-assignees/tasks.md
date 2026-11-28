EPIC: workflow-assignees (proposal.md, #426). Decisions: DEC-1 to DEC-10; design.md D-1 to D-8.

> Derives from: `proposal.md`. Appetite MEDIUM, two stages, one PR each.
> Review per stage: the appetite's review set (`develop/agents.adoc`).

## 1. Assign, guard, clear, record, PR 1, branch `feat/workflow-assignees`

- [x] 1.1 Lead: the model of [D-1](design.md#d-1) in `rp_workflow.yaml` and the vocabulary
  constants, then `make generate`, `make refresh-snapshot` (`model-shape.yaml`). Accept:
  `make check-quality`; the generated classes carry the new slots.
- [x] 1.2 The test fixtures of [D-8](design.md#d-8), in the new test file; the shared fixtures
  unchanged. Accept: the existing workflow tests stay green unchanged.
- [x] 1.3 Tests first: T1 to T13 (`design.md#tests`). RED: no `assign`, no `assignable`, no
  guard on `rp:assignedTo`.
- [x] 1.4 `load_workflow`: refuse a clearing edge on a workflow that is not assignable
  ([D-5](design.md#d-5), DEC-3, DEC-5). Accept: T1.
- [x] 1.5 The guard: `keep_state` keeps the assignees in its one query; `_allow_assignees` and
  the keyword-only `allowed_assignees` on the `WriteGuard.prepare` port and its test double
  ([D-2](design.md#d-2), DEC-2). Accept: T2, T3; `make test-changed check-quality`.
- [x] 1.6 `Assignments.assign`, `Collaboration.assign`, the `access_of` wiring in the kit, the
  `.importlinter` line ([D-3](design.md#d-3), [D-4](design.md#d-4), DEC-3, DEC-4, DEC-6, DEC-10).
  Accept: T4 to T11; `make check-architecture`.
- [x] 1.7 `assignments` and the shared provenance helper ([D-3](design.md#d-3), DEC-8). Accept:
  T13, and the existing transition-history tests unchanged.
- [x] 1.8 The clearing edge in `Transitions._store` ([D-5](design.md#d-5), DEC-5). Accept: T12.
- [ ] 1.9 Lead: `make refresh-surface` (the new public names), then the stage gate of
  `docs/modules/ROOT/pages/develop/agents.adoc#_the_gates` (`make check-all`,
  `make test-containers`), the review set, PR.

## 2. Release on lost access, the queue, docs, PR 2, branch `feat/assignee-release`

- [ ] 2.1 Tests first: T14 to T16. RED: grants removed, assignee kept.
- [ ] 2.2 `Assignments.release_unreadable`, `ServiceKit.release_assignees`, the call after
  `tenancy.set_grants` in `TenantApi.set_grants` ([D-6](design.md#d-6), DEC-7). Accept: T14, T16.
- [ ] 2.3 The queue listing ([D-7](design.md#d-7), DEC-9): no code change planned. Accept: T15;
  a red T15 stops the builder and goes to the developer.
- [ ] 2.4 Docs ([D-6](design.md#d-6), [Risks](design.md#risks--trade-offs)):
  `docs/modules/ROOT/pages/howto/workflow.adoc` gains a section "Assign the work" (assignable,
  `assign`, the clearing edge, `assignments`, the queue filter);
  `docs/modules/ROOT/pages/user-manual/access.adoc#_grant_and_prohibit` gains who may assign, the
  release, RISK-2 and RISK-3; `docs/modules/ROOT/pages/architecture/data-flows.adoc` (the
  `keep_state` paragraph also keeps the assignees, D-19); a MODIFIED delta of `rp-messages`
  naming the toolkit-filled slots `assigned_principals` and `released_principals` (D-19). Run
  `make refresh-surface`. Accept: `make check-docs`, `openspec validate --strict`.
- [ ] 2.5 Lead: the stage gate of `docs/modules/ROOT/pages/develop/agents.adoc#_the_gates`
  (`make check-all`, `make test-containers`), the review set, PR. Comment on #426 with the call,
  the filter and the release, for the consumer's change.

## 3. Close

- [ ] 3.1 Rows in `tests/audit/scenario-map.csv` for the new tests T1 to T16
  ([Tests](design.md#tests)), each stage adding its own; `make refresh-map` exits 0.
- [ ] 3.2 After the last merge: reconcile `proposal.md` with what shipped, archive the change
  (`/opsx:archive`), close #426.

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 1.4 · [ ] 1.5 · [ ] 1.6 · [ ] 1.7 · [ ] 1.8 · [ ] 1.9 ·
  [ ] 2.1 · [ ] 2.2 · [ ] 2.3 · [ ] 2.4 · [ ] 2.5 · [ ] 3.1 · [ ] 3.2

## Verification

Each stage: its T-rows go red, then green; `make check-all` and `make test-containers` before each
PR; `openspec validate workflow-assignees --strict`; the PLAN gated (`evidence/clarity-gate.md`).
