# Acceptance: uml-roles-and-workflows

- **Date:** 2026-11-21.
- **Who:** the developer, in the epic session.
- **Shown:** the EPIC's use cases run end to end on fixtures, through the command line and the library's own loaders:
  - the four feature scenarios in `tests/generator/feature/uml_import.feature`: three roles, an unknown level, a drawn workflow, an undefined role;
  - the signed-off scenarios proved in unit tests (traceability in `tests/audit/scenario-map.csv`).
- **Verdict:** accepted to merge both stages now (D-12b).
- **Open:** the run on the first consumer's real model. It stops at the model's own boundary with no root in its access package (D-8), so no roles or workflow file has yet been written from it. The rerun is an open item of `handover.md`, to be filled into `evidence/real-model-run.md` once the consumer fixes its model.
