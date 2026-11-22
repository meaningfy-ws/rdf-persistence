EPIC: slot-resolution (proposal.md, #277, #278). Decisions: design.md D-1 to D-7, DEC-1 to DEC-3.

Recorded after delivery: every task was done in PR #289, test first from the issue's toy
reproduction, one commit per issue.

## 1. The identifier is never a property (#277, commit `55932696`)

- [x] 1.1 Toy: `Template` gains a business `identifier` (`dcterms:identifier`, string). Tests first:
  TC-1, TC-3. RED: the toy's lock check stopped generation ("range changed … dcterms:identifier").
- [x] 1.2 The lock pairs the slots of one IRI (D-7). Test: TC-4.
- [x] 1.3 The identifier slot's property shape goes (D-1, D-4); referrer naming skips it (D-1).
  Accept: TC-1, TC-3 and TC-4 pass; `make test-fast` and `make test-generator` pass.

## 2. A slot name resolves to its owner's slot (#278, commit `d8fbd245`)

- [x] 2.1 Toy: `Template` gains its own `version` (`dcat:version`). Tests first: TC-1, TC-2, TC-3.
  RED: the context mapped `version` to `rp:version` while the mapper and the shapes used
  `dcat:version`.
- [x] 2.2 `prefer_application_slots` in `load_schema` and `apply_defaults` (D-2, D-3); closed shapes
  ignore the session's predicates by IRI.
- [x] 2.3 The hard rule `toolkit_slot_name` in `rp_generation.yaml` and `checks/hard.py` (D-2).
  Test: TC-5. Docs: `architecture/generation.adoc`.
- [x] 2.4 The bookkeeping test checks the resolved slot (D-5). Test: TC-6.

## 3. Close

- [x] 3.1 Scenario-map rows for the new tests; `make check-all`, `make test-containers`; one L2+L3
  review; GitNexus impact (D-6).
- [x] 3.2 Merged on green CI (`13af7af2`); #277 and #278 closed; mapping-workbench-v2 PR #101 told.
- [x] 3.3 This EPIC and PLAN recorded and archived (2026-11-22).
