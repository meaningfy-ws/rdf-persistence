> Derives from: EPIC `openapi-refusal-problems` (proposal.md), issue #457.

## 1. Stage 1: the document lists the refusal problems

- [x] 1.1 **unit + code** — design.md §Decisions PD-1 to PD-6, §Test cases TC-1 to TC-3b. Failing
  tests first in `tests/unit/api/test_openapi.py`, then `_refusal_components`,
  `_accepting_refusals` and their call sites in `install_openapi` (`api/entrypoints/openapi.py`);
  `install_service`'s docstring (`service.py:132-133`) says the classes are listed and its
  `Raises:` names the new `ValueError`. Accept: TC-1 to TC-3b pass; `test_openapi_served` and
  `test_rule_refusal.py` pass unedited; task gate green.
- [ ] 1.2 **contract + tsc** — after 1.1; design.md PD-7, TC-4. The contract cases of TC-4 in
  `tests/unit/api/test_contract.py`; `tests/dump_openapi.py` registers `HeldKeyProblem`. Accept:
  TC-4 passes; `make typecheck-openapi-ts` green; task gate green.
- [ ] 1.3 **docs** — beside 1.1 (disjoint files). `architecture/api.adoc:210` and
  `user-manual/access.adoc:319` say the document lists the registered classes (components, the
  create/replace 409/422 and every `default`, the start-up `ValueError` on a taken name); the
  `CHANGELOG.md` Unreleased entry of `consumer-write-rules` drops "does not yet list the classes"
  and an Added line names this change and #457. Accept: `make check-docs` green.

## Roadmap

- [ ] 1.1 ∥ 1.3 → 1.2 → review (one L1–L5 pass) + checker → fix to the floor → `make check-all`

## Verification

TC-1 to TC-4 in the unit lane, `make typecheck-openapi-ts`, `make check-all`; the PLAN gated
≥ 9/10 (`evidence/clarity-gate.md`).
