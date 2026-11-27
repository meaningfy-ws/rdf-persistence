<!-- Parents: archive/2026-11-27-typescript-toolkit-modules (its Reconciliation table, design.md
     D-4, D-7); the checker's reconcile pass of 2026-11-28 against develop 677e8949 (R-1 to R-11). -->

# EPIC: reconcile typescript-toolkit-modules with what was built

## Appetite

**SMALL.** Tests, one toy schema slot (and its regenerated files), docs and spec text. No change
to the generator's code.

## Why

A fresh checker compared the archived EPIC `typescript-toolkit-modules` with the code as merged
(677e8949) and found eleven deviations (R-1 to R-11). Two are promises made without proof: the
scenario "`tsc --strict` compiles both folders" never compiles a toolkit import, because the toy
imports no toolkit type (R-1), and DEC-5 has no test (R-2). Others are weak or missing tests (R-6,
R-7), text that says less or more than the code (R-4, R-10, R-11), and records (R-3, R-5, R-8, R-9).

## Solution outline

Make the toy prove the shaped behaviour: a toy class in the technical schema gets a slot ranged on
a toolkit type, so `make generate` writes an import from the owner's folder into
`web/src/services/generated/` and `make typecheck-ts` compiles it. Add the missing tests. Correct
the docs. State in the living spec what the key does to the freshness inputs (PD-6). Record the
rest here.

## Key decisions

- **DEC-1 (R-1):** the toy's technical schema (`services/loan_checks_response.yaml`) gains one
  optional slot ranged on a toolkit enum or served type (not an identified class: a reference to an
  identified class renders as a `string`, with no import). Reason: the signed-off scenario names
  `tsc`; only a committed toolkit import in the toy reaches `make typecheck-ts` and CI's types job.
  Rejected: rewording the scenario (it would weaken what the developer signed off).
- **DEC-2 (R-2, R-6, R-7):** tests in `tests/generator/unit/test_typescript_toolkit_owner.py`: a
  toolkit module outside the shared set is written and exported by an importer; `toolkit=None`
  equals the committed toy domain tree (not itself); a toolkit specifier from an owner nested under
  the importer starts with `./`; one TypeScript entry with the key writes the same files as without.
- **DEC-3 (R-3, R-8):** no code. `render` with `toolkit` and no `folder` copies every module; the
  step always passes a folder, so it is recorded as an Error-matrix row in this change's design, not
  refused. The hand-edited copy is kept by `pipeline._remove_stale` as for any stale output; its
  existing test is cited, not duplicated.
- **DEC-4 (R-4, R-10, R-11):** docs: `generation.adoc` says "the same folder" (no normalisation
  claim) and "every metamodel module that has classes or enums"; `user-manual/generate.adoc`'s key
  row says the key makes the metamodel's files freshness inputs of that entry. The living spec
  states the inputs and DEC-5 as scenarios (this change's delta).
- **DEC-5 (R-5, R-9):** records only. DEC-3 of the archived change named three refusals; four were
  delivered (PD-2 added the shared folder). PD-3 named two cached functions; one cached `_shared`
  serves both. The archive stays as written; this proposal is the record.

## Rabbit-holes

- **The toy slot ripples.** A new slot changes the toy's Python, shapes, context, frames and
  TypeScript, and possibly goldens. Only `make generate` writes them; the builder reports the diff
  and the lead checks that every change follows from the one slot.

## No-gos

- Any change to `rdf_persistence_generation/` code.
- Editing the archived change.

---

## What Changes

- The toy's technical schema gains one slot on a toolkit type; its regenerated trees carry a
  toolkit import from the owner's folder.
- New tests for DEC-5, the `./` toolkit specifier, one TypeScript entry with the key, and a real
  baseline for `toolkit=None`.
- `generation.adoc`, `user-manual/generate.adoc` corrected.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rp-generation`: "The toolkit's TypeScript has one owner in a project" states the owner's
  freshness inputs and gains two scenarios.

## Impact

- Toy: `tests/fixtures/library/services/loan_checks_response.yaml` and its generated files.
- Tests: `tests/generator/unit/test_typescript_toolkit_owner.py`; scenario-map rows.
- Docs: `architecture/generation.adoc`, `user-manual/generate.adoc`.
