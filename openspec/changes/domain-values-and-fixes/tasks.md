EPIC: domain-values-and-fixes (proposal.md, #301, #303, #302, #300). Decisions: DEC-1 to DEC-9; design.md.

## 1. Value modules (#301), PR 1, branch `feat/domain-value-modules`

- [x] 1.1 Tests first: TC-1, rows E1 to E14 (`design.md#error-matrix`, scratch projects). RED:
  ownership and folder problems for a value module. Layer: generator checks.
- [x] 1.2 `ModuleKind.value` in `rp_core.yaml`, `make generate` (DEC-1); the boundary and hard checks
  learn the kind (DEC-2 to DEC-5, D-1, D-2; `design.md#algorithm` table). Accept: TC-1 green;
  `make test-changed check-quality`.
- [x] 1.3 Toy: `values/loan_checks.yaml`, its target, a technical module importing it (TC-2, D-3,
  `design.md#example-the-toy-testsfixtureslibrary`);
  `architecture/generation.adoc` gains a "Value modules" section and the module-kind list names
  `value`; `questions.adoc` gains the question if a new page is made (none planned). Accept: TC-2,
  TC-3.
- [x] 1.4 Lead: impact, `make check-all`, L2+L3 review, fix pass, PR.

## 2. A reference to an abstract root is an IRI (#303), PR 2, branch `fix/abstract-root-reference`

- [x] 2.1 Tests first: TC-4, TC-5 on the toy (abstract `LendingItem` and a slot over it, D-13).
  RED: `lends: Item`.
- [x] 2.2 Root cause, then the fix where every generator reads it (DEC-6, D-11,
  `design.md#2-a-reference-to-an-abstract-root-303`). Accept: TC-4, TC-5; the
  regenerated diff holds only slots over abstract roots (RISK-3).
- [x] 2.3 Lead: impact (D-12), `make check-all`, L2+L3 review, PR marked BREAKING in generated code
  (RISK-2).

## 3. The strategy honours `slot_usage` (#302), PR 3, branch `fix/strategy-slot-usage`

- [x] 3.1 Tests first: TC-6 on the toy (`BookCollection`, `Display`). RED as in the issue.
- [x] 3.2 Root cause, then the fix in `strategies.py` and the context extension (DEC-7, D-14, D-15,
  `design.md#3-the-strategy-honours-slot_usage-302`). Accept: TC-6.
- [x] 3.3 Lead: `make check-all`, L2+L3 review, PR.

## 4. The version helpers are public (#300), PR 4, branch `fix/export-version-helpers`

- [x] 4.1 Tests first: TC-7. RED: `AttributeError`.
- [x] 4.2 Lazy exports, `__all__`, `make refresh-surface`, docs (DEC-8,
  `design.md#4-the-version-helpers-are-public-300`). Accept: TC-7, TC-8.
- [x] 4.3 Lead: `make check-all`, L2+L3 review, PR.

## 5. Close

- [x] 5.1 Scenario-map rows for the new tests (each stage adds its own).
- [ ] 5.2 After the last merge: archive the change, tell MWB2 (#301 unblocks v2-05 stage 1).
