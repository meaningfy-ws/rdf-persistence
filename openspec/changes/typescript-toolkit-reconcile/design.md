# Design: typescript-toolkit-reconcile

> Derives from: EPIC `typescript-toolkit-reconcile` (proposal.md, DEC-1 to DEC-5). The deviations
> R-1 to R-11 are the checker's of 2026-11-28 (proposal.md, Why).

## Decisions

- **PD-1 The toy slot (DEC-1).** In `tests/fixtures/library/services/loan_checks_response.yaml`,
  one class gains one optional, single-valued slot ranged on a toolkit enum or a served type that
  the technical schema can import (check what it already imports; add the import of the toolkit
  module if needed, the way the toy's other schemas do). Prefer an enum of `rp_core` or a type of the
  served schemas. After `make generate` (in the builder's own worktree), the technical tree's module
  imports that type `from "../../domain/generated/<module>"` and `make typecheck-ts` passes. Every
  other diff must follow from the slot (Python field, shapes, context, frames, OpenAPI components,
  manifests); the toy's domain tree stays byte-identical.
- **PD-2 The tests (DEC-2)**, in `tests/generator/unit/test_typescript_toolkit_owner.py`:
  - R-2: an importer render of a temporary schema that imports a toolkit module outside
    `_shared_names()` (a technical toolkit module, by absolute path as the file's existing temporary
    schemas do) writes that module's file and `index.ts` exports it.
  - R-6: `render(domain schema, folder=<domain folder>)` with no toolkit equals the toy's committed
    domain tree file by file (replacing the self-comparison); and `_write_typescript`-level or
    `run_toy`-level: one TypeScript target with the key writes the same files as without it.
  - R-7: `_importing_toolkit` (or `render`) with the owner's folder nested under the importer's
    yields a specifier starting with `./`.
- **PD-3 Docs (DEC-4).** As DEC-4 says; `make check-docs`.

## Error matrix (additions to the archived one)

| Input / state | Behaviour |
|---|---|
| `render(..., toolkit=<folder>)` with no `folder` | every module is copied, as with no toolkit; the step always passes a folder (R-3) |
| An importer's earlier copy edited by hand | kept with a problem by `pipeline._remove_stale`, as for every stale output; proved by that function's existing tests (R-8) |

## Test plan

| TC | Scenario | Proof | Tier |
|---|---|---|---|
| TC-1 | two TypeScript targets and an owner (R-1) | the toy's committed technical tree imports a toolkit type from `../../domain/generated/`; the existing toy-tree tests pin it; `make typecheck-ts` compiles it | generator unit; `make check-types` |
| TC-2 | a toolkit module outside the shared set (R-2) | PD-2 first bullet | generator unit |
| TC-3 | one TypeScript target (R-6) | PD-2 second bullet | generator unit |
| TC-4 | nested owner folder (R-7) | PD-2 third bullet | generator unit |
| TC-5 | the owner's freshness inputs (R-11) | the existing `test_a_target_with_the_key_lists_the_metamodel_files_as_inputs`, mapped to the new scenario | generator unit |

## Delivery decisions

- **D-1 Review (one pass L2+L3, PR #438): no Critical as labelled; four re-labelled Critical.**
  Reason for each re-label: this change exists to make the shape's proofs and texts true, and each
  of these leaves one untrue.
  - **F1 (W1)** — no test pins the toy's toolkit import, so dropping the slot would silently lose
    R-1's proof. Fix: assert the import in the toy technical-tree test; map it to TC-1.
  - **F2 (W2)** — the R-2 test's schema keeps a range (`Authorised`) it no longer imports. Fix: its
    own small schema importing only the non-shared toolkit module.
  - **F3 (W3)** — `user-manual/generate.adoc`'s `typescript` output row implies every target writes
    `rp_service.ts`. Fix: name `rp_service.ts` with the metamodel modules as the owner's.
  - **F4 (S5)** — `test_without_a_toolkit_the_domain_render_is_today_s` now checks owner render ==
    plain render, but its name and map row say `toolkit=None`. Fix: rename and remap it to "two
    TypeScript targets and an owner".

  Under the floor: S4 (the inputs scenario's map row says `--check` reports stale; the test checks
  `current_inputs`: confidence kept), S6 (the hand-edited copy's test is not named here: it is
  `tests/generator/unit/test_generation_inputs.py::test_a_listed_file_that_changed_since_it_was_generated_is_kept_and_reported`).

## Risks

- **RISK-1 the toy slot changes goldens.** Mitigation: only `make generate` writes them; the lead
  reads the diff and rejects any change that does not follow from the slot.
