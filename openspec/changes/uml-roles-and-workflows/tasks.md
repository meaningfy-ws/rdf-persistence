EPIC: uml-roles-and-workflows (proposal.md), issue #245 parts 2 and 3. Decisions: DEC-1 to DEC-8; design.md PD-1 to PD-8; owner answers in inputs/qa.md; probe in inputs/probe.md.

Every task: the failing test first, in the tier named; task gate `make test-changed check-quality`;
commit body `Refs: uml-roles-and-workflows <task> <PD>`. Builders never commit; the lead does. Two
stages, one PR each, each merged on green CI (P-0013). Records change through
`rp_generation.yaml` and `make generate`, never by hand.

## 1. Stage 1: role definitions

- [x] 1.1 Reader and records (PD-1, PD-2). Generator unit, first, in
  `tests/generator/unit/test_uml_qea.py`: a `QeaBuilder` model with one `Object` (classifier → a
  drawn `rp:RoleDefinition`, a `RunState`) reads into one `UmlObject` with its three `run_values`;
  a `.qea` lacking `t_object.RunState` is a usage error naming the column. Then `QeaBuilder`
  columns and `object_(...)`, `TABLE_COLUMNS`, `UmlObject`/`UmlRunValue` in `rp_generation.yaml`,
  `make generate`. Accept: `test_uml_qea_fixture.py` and `test_uml_golden.py` unchanged and green.
- [x] 1.2 Role rule (PD-3), after 1.1. Generator unit, first,
  `tests/generator/unit/test_uml_roles.py`, one parametrized table per error-matrix row of an
  Object (valid entry; classifier a domain class; classifier 0; `level=planet`; action `fly`; empty
  actions; repeated action; unknown variable; variable twice; missing `role`; `Op` not `=`; two
  objects with one level and role), each asserting the problem text names the object. Then
  `uml/roles.py` and its call in `convert`, `ReportKind.ROLE`, the `UmlRule` codes.
- [x] 1.3 Write and final check (PD-3, PD-4), after 1.2. Generator unit, first, in
  `test_uml_write.py`: `<root>.roles.yaml` written in `(role, level)` order and read back by
  `load_role_definitions`, its text equal to PD-6's `safe_dump` call; no objects → no file; a second
  run byte-identical; a stray `<root>.roles.yaml` with no objects drawn → **no** `stale-file` line
  and the report as before; with roles drawn and a stray `*.roles.yaml` of another root name in `--out` → `stale-file`; a staged
  file the loader refuses (patched loader) → nothing moved, and in `test_uml_cli.py` exit 1 with
  `rp-uml2linkml: <message>`. Then `convert`'s `files` (PD-8), `write(files=)`,
  `StagedFileRefused`, its handling in `cli.py`.
- [x] 1.4 Acceptance and docs (PD-7), after 1.3. Generator feature, first: two scenarios in
  `uml_import.feature` (three roles accepted; `level=planet` refused naming the object). Then the
  UML conventions section with a PlantUML object-diagram snippet and the file it becomes; the
  how-to's `install_service(rules=...)` line. Run on the probed model (read-only copy), record
  counts in `evidence/real-model-run.md`. Accept: `make check-docs` green.

## 2. Stage 2: workflows

- [x] 2.1 Reader and records (PD-1, PD-2). Generator unit, first, in `test_uml_qea.py`: a model
  with a Statechart diagram, an Initial node, two States and two StateFlows (tags in
  `t_connectortag`) reads into `UmlStatechart`, `UmlStateNode`s and `UmlStateFlow`s; a StateFlow
  with one end outside the subtree is `no_rule`; a substate (`ParentID` ≠ 0), a State owning a
  `t_operation` row, a StateFlow with a `Name`, `PDATA2`, `Stereotype` or a `t_xref` trigger row are
  each `no_rule`; a `<memo>` tag is read from `NOTES`; a model with neither reads as today. Then
  `QeaBuilder` (`state`, `statechart`, `state_flow`, the two tables), `TABLE_COLUMNS`, the records,
  `make generate`.
- [ ] 2.2 Workflow rule (PD-5), after 2.1. Generator unit, first,
  `tests/generator/unit/test_uml_workflows.py`, one parametrized table covering every error-matrix
  row of State node, Diagram, StateFlow, Class and Workflow, each asserting the element named; the
  CURIE name and the plain name (`derived-iri` line); two diagrams with one name; a class tagged
  `workflow=x` with no Statechart converted converts as today (the existing
  `test_uml_rules.py:1039-1042` row stays green); the design's concrete example. Then
  `uml/workflows.py` and its call in `convert` after roles, `ReportKind.WORKFLOW`/`DERIVED_IRI`,
  the `UmlRule` codes.
- [ ] 2.3 Write and final check (PD-4, PD-6), after 2.2. Generator unit, first, in
  `test_uml_write.py`: the concrete example's file, byte for byte; read by `load_workflow`; rerun
  identical; `out/workflows/` holding another file: the new file moved in beside it (no
  `ENOTEMPTY`), `stale-file workflows/x.workflow.yaml` when a workflow is drawn, no line when none
  is. Then the per-file move in `write`.
- [ ] 2.4 Acceptance and docs (PD-7), after 2.3. Generator feature, first: two scenarios in
  `uml_import.feature` (a four-state, five-transition workflow accepted; an undefined role refused).
  Then the UML conventions section with a PlantUML state-diagram snippet and its file; the how-to's
  `workflows=[...]` line and RISK-3's order note. Run on the probed model, add to
  `evidence/real-model-run.md`. Accept: `make check-docs` green.

## 3. Roadmap

Stage 1 (1.1 → 1.2 → 1.3 → 1.4), then stage 2 (2.1 → 2.2 → 2.3 → 2.4). Stage 2 starts after
stage 1 merges. For the first consumer it is useful only once `module_kind` (part 1, separate)
lands (RISK-3). Lead gates per stage: `make check-all`, `make test-generator`; review by one pass
per stage (P-0005).

## 4. Tests moved or rewritten

None moved. `QeaBuilder` gains columns and tables; every existing generator test keeps running in
the generator lane (`make test-generator`) and still proves the stage-1 rules of uml-to-linkml.
