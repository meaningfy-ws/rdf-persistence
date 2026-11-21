<!-- PLAN (design half) of uml-roles-and-workflows. PLAN = this file + tasks.md.
     Read against develop 4a22f06e. Evidence: inputs/probe.md (temp/uml-probe/roles_workflows.py). -->

# Design: uml-roles-and-workflows

> Derives from: EPIC `uml-roles-and-workflows` (proposal.md), DEC-1 to DEC-8; issue #245 parts 2
> and 3; owner's answers in inputs/qa.md; probe in inputs/probe.md.

## Context

Facts (develop `4a22f06e`, and the probe):

- F-1: `uml/qea.py` reads `t_object` (`Object_ID, Object_Type, Name, Alias, Note, Package_ID,
  Stereotype, Abstract, ea_guid`), `t_attribute`, `t_connector`, `t_objectproperties`, `t_xref`,
  `t_package`, `t_diagramobjects` (boundaries); `_check_schema` refuses a file lacking a read column
  (usage error, exit 2). Each object of another type in the converted subtree is a `no_rule`
  problem (`read`, :285); a connector with no converted class at an end is skipped silently (:412).
  Of `t_connector` it reads `PDATA1` and `Stereotype` but not `Name`, `PDATA2`-`PDATA5` or `ea_guid`
  (`TABLE_COLUMNS`, `qea.py:60-76`); a `<memo>` tag value is read from `Notes` (:470).
- F-2: a drawn class named like a toolkit class is recorded in `ctx.drawn_toolkit[object_id]` and
  not generated (R-28, `classes.py:89`).
- F-3: `convert` (`uml/convert.py:369`) is pure and returns `(schemas, report, problems)`; any
  problem → exit 1, nothing written. `write` (`uml/write.py:48`) stages files and moves them with
  `os.replace`; a stray `<root>_*.yaml` gets a `stale-file` line, never deleted.
- F-4: report lines are `ctx.findings.note(ReportKind, element, message)`; problems
  `ctx.findings.problem(UmlRule, element, message)` / `no_rule`. Both enums and the UML records are
  generated from `rdf_persistence_generation/model/rp_generation.yaml` (D-24).
- F-5: the generator package already imports the library (`lock_step.py`, `steps.py`); the library
  never imports the generator. So the converter may validate with the library's generated
  `RoleDefinition` and `Workflow` and with `load_role_definitions` / `load_workflow`.
- F-6: the probe: role objects are `Object` rows with `Classifier` → the drawn `rp:RoleDefinition`
  and `RunState` `@VAR;Variable=<v>;Value=<x>;Op==;@ENDVAR;` triples; states are `State` and
  `StateNode` (`NType=3` Initial) rows with `ParentID=0`, grouped only by a `Statechart` diagram;
  transitions are `StateFlow` connectors, tags in `t_connectortag (ElementID, Property, VALUE)`, no
  name or PDATA; the transition leaving the Initial node has no tags.
- F-7: `naming.py` splits `pfx:Local` and expands it with the prefixes file; an unknown prefix is a
  problem (PD-6 of uml-to-linkml).

## Goals / Non-Goals

**Goals**
- G-1 (stage 1): each `rp:RoleDefinition` object becomes one entry of `<root-name>.roles.yaml` that
  `load_role_definitions` reads; every invalid value fails the run naming the object.
- G-2 (stage 2): each Statechart diagram becomes `workflows/<name>.workflow.yaml` that
  `load_workflow` reads; every invalid construct fails the run naming the element.
- G-3: a model with neither converts byte for byte as before; a rerun is byte-identical.

**Non-Goals**: the EPIC's no-gos (`module_kind`, StateMachine elements, final and other
pseudostates, guards, XMI, the «workflow states» comparison).

## Decisions

- **PD-1 Reading (stage 1 adds the object columns, stage 2 the rest).** `TABLE_COLUMNS` gains
  `t_object.Classifier` and `RunState` (stage 1), `t_object.NType`, `t_diagram (Diagram_ID, Name,
  Package_ID, Diagram_Type)`, `t_connectortag (ElementID, Property, VALUE, NOTES)`,
  `t_object.ParentID`, `t_connector.Name`, `PDATA2`-`PDATA5`, `Stereotype`, `ea_guid`, and
  `t_operation.Object_ID` (stage 2). Every EA
  `.qea` has them (EA's fixed repository schema); the builder `tests/generator/uml_qea.py`
  (`QeaBuilder`) creates them. In the converted subtree: `Object` rows become `UmlObject` records;
  `State` and `StateNode` rows become `UmlStateNode` records (stage 2; in stage 1 they stay
  `no_rule`, as today). A `StateFlow` with both ends on state nodes of the subtree becomes a
  `UmlStateFlow` (stage 2); one with one end outside the subtree is a `no_rule` ("crosses the
  converted packages"). Constructs the probe did not see fail (DEC-6), each as `no_rule` naming
  it: a state node with `ParentID` ≠ 0 (a substate); a State owning `t_operation` rows (entry, do or
  exit behaviour); a StateFlow with a `Name`, a non-empty `PDATA1`-`PDATA5`, a `Stereotype`, or a
  `t_xref` row whose `Client` is its `ea_guid` (where EA keeps triggers). A `<memo>` tag value is
  read from `NOTES`, as for class tags.
- **PD-2 Records** (in `rp_generation.yaml`, generated, D-24):
  - `UmlObject`: `object_id`, `uml_name`, `classifier_id`, `package_path`, `run_values`
    (multivalued `UmlRunValue`: `variable`, `value`, `operator`).
  - `UmlStateNode`: `object_id`, `uml_name`, `node_kind` (enum `state`, `initial`), `note`.
  - `UmlStateFlow`: `connector_id`, `source_id`, `target_id`, `uml_tagged_values`.
  - `UmlStatechart`: `diagram_id`, `uml_name`, `package_path`, `node_ids`.
  - `UmlModel` gains `uml_objects`, `uml_state_nodes`, `uml_state_flows`, `uml_statecharts`.
  - `ReportKind` gains `role`, `workflow`, `derived_iri`; `UmlRule` gains the problem codes of
    PD-3 and PD-5.
- **PD-3 Roles (stage 1, `uml/roles.py`).** For each `UmlObject`:
  1. its classifier must be in `ctx.drawn_toolkit` as `RoleDefinition`, otherwise `no_rule`
     ("Object of <classifier label>"; classifier 0 → "Object without a classifier");
  2. `RunState` is parsed with one pattern, `@VAR;(?P<body>.*?)@ENDVAR;`, each body split on `;`
     into `key=value` (split once at the first `=`); keys other than `Variable`, `Value` and `Op`
     (EA writes `Note=`) are ignored; non-blank text outside the blocks is a problem. A body without `Variable` or `Value`, an `Op`
     other than `=`, a variable other than `role`, `level`, `actions`, a variable given twice, or a
     missing one is a problem naming the object and the variable;
  3. the entry `{role, level, actions}` (actions split on `,`, each stripped, empties dropped, order
     kept, a repeat a problem, **none left a problem** naming the object, since the generated
     class accepts `[]` and only the loader refuses it) is validated with the library's `RoleDefinition.model_validate`; a
     `ValidationError` becomes one problem naming the object and the field (so the levels and
     actions are the toolkit's, not a copy, F-5);
  4. two objects with one `(level, role)` is a problem naming both.
  Entries are sorted by `(role, level)`. The file is PD-6's `yaml.safe_dump` call on the list of
  `{"role", "level", "actions"}` mappings, written by `write` beside the schemas. A `role` report
  line per entry: `role\t<object>\t<role> at <level>: <actions>`. No objects → no file.
- **PD-4 Final check.** After staging and before `os.replace`, `write` calls
  `load_role_definitions` (stage 1) and `load_workflow` (stage 2) on the staged files; an error there
  means PD-3/PD-5 missed a rule: `write` raises `StagedFileRefused` (a new `RuntimeError` subclass
  in `uml/write.py`), `cli.py` catches it and exits 1 printing `rp-uml2linkml: <loader message>`,
  and nothing is moved. The service-start checks across workflows (`Workflows._check`,
  `workflows.py:85-100`) are not run here; PD-5 covers the ones a drawing can break. Stale files
  are reported **only when the run draws at least one role** (for any `*.roles.yaml` other than the
  one it writes) **or one
  workflow** (for `workflows/*.workflow.yaml`): such a file in `--out` that this run did not write
  gets a `stale-file` line naming its path relative to `--out` (`workflows/<f>`). A model that draws
  neither leaves hand-written files unreported, so its report stays as before (G-3).
- **PD-5 Workflows (stage 2, `uml/workflows.py`).** For each `UmlStatechart` in the subtree:
  1. Name: `naming.py` on the diagram name. `pfx:local` → IRI = expansion, name = `local`; a plain
     `local` → IRI = `schema_base` + `workflows/` + `local` and a `derived_iri` line (DEC-4). The
     name must match `workflow_name`'s pattern, checked by `Workflow.model_validate` (F-5).
  2. Nodes: its `node_ids` among the state nodes. A state node of the subtree on no Statechart
     diagram, or on two, is a problem naming it. A `StateNode` whose `NType` is not 3 is `no_rule`
     ("StateNode kind <NType>"), DEC-6.
  3. Initial: exactly one Initial node; exactly one `StateFlow` leaves it, with no tags, to a
     `State` of the same diagram: its name is `initial_state`. Otherwise a problem naming the
     diagram (none / several) or the transition (tags).
  4. States: the `State` names as drawn, sorted; two equal names are a problem.
  5. Transitions: every other `StateFlow` between the diagram's nodes, with tags `roles` (required,
     comma-separated, stripped, non-empty) and `comment_required` (optional, `true`/`false` exactly,
     default absent). Another tag, a name, any non-empty `PDATA1`–`PDATA5`, a transition into the
     Initial node, or one whose ends are on different diagrams is a problem naming the transition
     (`<source> -> <target>`). A role not among the drawn role definitions' `role` values (any level)
     is a problem naming the transition and the role (DEC-5). Transitions sorted by `(from, to)`; two
     with the same `(from, to)` are a problem.
  6. `Workflow.model_validate({id, workflow_name, workflow_states, initial_state,
     workflow_transitions})`: a `ValidationError` becomes a problem naming the diagram.
  7. A `workflow` report line per workflow: `workflow\t<diagram>\t<n> states, <m> transitions`.
  Then, across the model: two Statechart diagrams with one workflow name or one IRI are a problem
  naming both. **When the converted subtree holds at least one Statechart diagram**, every class
  `workflow` tag (as `apply_tags` reads it) must name a converted workflow, otherwise a problem
  naming the class. With no Statechart diagram converted (none drawn, or their package excluded) the
  tag is converted exactly as today, unchecked (the existing test
  `test_uml_rules.py:1039-1042` and the consumer's run with its workflow package excluded keep
  passing). This is the PLAN's reading of DEC-3, kept consistent with G-3 and the spec's "converts
  as before"; the owner may overrule. A workflow no class names gets a report line `workflow …
  named by no class` (not a failure: the class may be in an excluded package). An unknown diagram
  prefix is reported by `naming.py` under the `class_iri` rule, once per prefix
  (`context.py:157-160`), as for classes.
- **PD-6 Write.** `workflows/<name>.workflow.yaml` under `--out`, the keys in the order of
  `tests/fixtures/library/review.workflow.yaml` (`id`, `workflow_name`, `workflow_states`,
  `initial_state`, `workflow_transitions`; transitions as `from_state`, `to_state`,
  `transition_roles`, `comment_required` only when true). Both files are written with
  `yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)`, block style (PyYAML
  cannot emit the fixture's indented flow mappings); the example below is that call's output. The
  workflow files are staged in `<stage>/workflows/` and moved **file by file** into
  `out/workflows/` (created if missing), never by replacing the directory, since it may hold the
  consumer's other files.
- **PD-8 Data path.** `convert` returns `(schemas, report, problems, files)`, `files` a
  `dict[str, str]` from a path relative to `--out` to its text (empty when nothing is drawn); `write`
  gains `files: Mapping[str, str] | None = None` and stages, checks (PD-4) and moves them with the schemas.
  `cli.py` passes it through and handles `StagedFileRefused` (PD-4). No new record: the files are
  plain text, the UML records stay D-24's.
- **PD-7 Docs (P-0014).** `reference/uml-conventions.adoc`: one section per stage, each with a UML
  snippet (PlantUML: an object diagram of `rp:RoleDefinition` instances; a state diagram) and the
  file it becomes; `howto/uml-to-linkml.adoc`: passing the written files to `install_service(rules=,
  workflows=)`.

## Concrete example (stage 2)

Diagram `lib:loan` (prefix `lib` → `https://example.org/ns/library/`), nodes: Initial, `requested`,
`approved`, `refused`, `returned`; flows: Initial→requested; requested→approved `{roles=librarian}`;
requested→refused `{roles=librarian, comment_required=true}`; approved→returned
`{roles=librarian,reader}`; refused→requested `{roles=reader}`. Roles drawn: `librarian`, `reader`.
Written `workflows/loan.workflow.yaml`:

```yaml
id: https://example.org/ns/library/loan
workflow_name: loan
workflow_states:
- approved
- refused
- requested
- returned
initial_state: requested
workflow_transitions:
- from_state: approved
  to_state: returned
  transition_roles:
  - librarian
  - reader
- from_state: refused
  to_state: requested
  transition_roles:
  - reader
- from_state: requested
  to_state: approved
  transition_roles:
  - librarian
- from_state: requested
  to_state: refused
  transition_roles:
  - librarian
  comment_required: true
```

## Error matrix

| Element | Case | Result (exit 1, nothing written unless stated) |
|---|---|---|
| Object | classifier not the drawn `rp:RoleDefinition`, or 0 | `no_rule` naming the object |
| Object | `level=planet`, action `fly`, empty `actions`, unknown variable, `Op` not `=` | problem naming the object and the value |
| Object | two with one `(level, role)` | problem naming both |
| State node | NType ≠ 3 (final, choice, …) | `no_rule` naming it |
| State node | on no Statechart diagram / on two | problem naming it |
| Diagram | no Initial / two Initials / Initial with 0 or 2 outgoing | problem naming the diagram |
| Diagram | name `zz:loan` with unknown prefix | problem (F-7) |
| Diagram | plain name `loan` | **written**, `derived-iri` report line |
| Diagram | name `Loan_Flow` (breaks the pattern) | problem naming the diagram |
| StateFlow | tag other than `roles`/`comment_required`, `comment_required=yes` | problem naming the transition |
| StateFlow | a name, PDATA set | `no_rule` naming it (PD-1) |
| StateFlow | no `roles`, or a role not drawn | problem naming the transition (and role) |
| StateFlow | into Initial, across diagrams, duplicate `(from, to)` | problem naming it |
| StateFlow | one end outside the converted packages | `no_rule` |
| Class | `workflow=loan` and no drawn `loan` | problem naming the class |
| Workflow | named by no class | **written**, report line |
| Model | none of these | output byte-identical to before |
| Staged file | the library loader refuses it | exit 1, `rp-uml2linkml: <loader message>` (`StagedFileRefused`, a converter bug), nothing moved |
| Object | `RunState` with `Note=` keys / with text outside the `@VAR` blocks | keys ignored / problem naming the object |
| Object | `actions=` with no action left after splitting | problem naming the object |
| State node | `ParentID` ≠ 0 (substate); a State owning operations (entry/do/exit) | `no_rule` naming it |
| StateFlow | a `Stereotype`, or a `t_xref` row on its guid (trigger) | `no_rule` naming it |
| StateFlow | `roles` given as a `<memo>` tag | value read from `NOTES` |
| Diagram | two with one workflow name or one IRI (`lib:loan`, `oth:loan`) | problem naming both |
| Class | `workflow=x` and **no** Statechart diagram converted | as today: annotation written, unchecked |
| Out dir | holds hand-written `workflows/*.workflow.yaml`, run draws no workflow | no `stale-file` line; report as before |
| Out dir | holds `workflows/old.workflow.yaml`, run draws `loan` | `stale-file workflows/old.workflow.yaml`; `loan` moved in beside it |

## Anti-patterns

| Don't | Do | Why |
|---|---|---|
| Copy `RoleLevel`, `Action` or the name patterns into the converter | validate with the library's `RoleDefinition` / `Workflow` (F-5) | one source; a new action needs no converter edit |
| Trust `model_validate` alone for `actions` | refuse an empty list in PD-3 | the generated class accepts `[]`; the loader would fail later without naming the object |
| Check a column the reader does not read (PDATA, Name) | add it to `TABLE_COLUMNS` first (PD-1) | a check on a missing field passes silently |
| Replace `out/workflows/` with `os.replace` of a directory | move file by file (PD-6) | the directory may hold other files; `ENOTEMPTY` |
| Report stale roles or workflow files when none are drawn | report only when the run draws that kind (PD-4) | a hand-written file is not stale; G-3 |
| Require a class's `workflow` tag to match while no Statechart is converted | check only when one is converted (PD-5) | the workflow package may be excluded; models converting today must still convert |
| Rewrite EA names into snake case; order by EA ids | use names as drawn; order by name | ids change across EA edits; reruns must be byte-identical |
| Read diagram layout beyond membership | `t_diagramobjects` rows only | layout is not meaning |

## Test coverage

Generator unit tier, `tests/generator/unit/test_uml_roles.py` and `test_uml_workflows.py`, with
`QeaBuilder` gaining `object_(…, classifier, run_state)`, `state(…, ntype)`, `statechart(name,
package, nodes)`, `state_flow(source, target, tags)`: one row per error-matrix line, positive and
negative; the byte-identical rerun; the "none drawn" equality against the existing fixture's
output. Generator feature tier: new scenarios in `tests/generator/feature/uml_import.feature`
(steps in `test_uml_import.py`), the issue's acceptance: three roles accepted by
`load_role_definitions`, a `level=planet` object refused; a four-state, five-transition workflow
accepted by `load_workflow`, an undefined role refused. The
real model run is recorded in `evidence/real-model-run.md` (counts only), as in uml-to-linkml.

## Risks / Trade-offs

- **RISK-1**: other EA versions or habits store a state machine differently (a StateMachine
  element owning states, `ParentID` set). Likelihood medium for a second consumer, low for the first.
  Impact: the run fails naming the element (DEC-6), so nothing is silently wrong. Accepted; a follow-up
  issue adds the encoding when a model needs it.
- **RISK-2**: the first consumer's diagram has a plain name, so its workflow IRI is derived until
  it renames the diagram. Accepted (DEC-4); the `derived-iri` line tells it. The derived IRI
  (`schema_base` + `workflows/<name>`) equals the consumer's hand-written `id` today. Renaming the
  diagram later to a CURIE changes the workflow's IRI, which must stay stable once data names it:
  the docs say to choose the name before the first data is stored.
- **RISK-5**: other EA behaviours a state machine can carry (entry/do/exit operations, triggers)
  are now refused (PD-1); one the PLAN did not foresee would be dropped silently. Likelihood low;
  the real-model run (task 2.4) lists every table row the subtree's state elements own.
- **RISK-3**: the consumer converts with its access package excluded until `module_kind` lands
  (DEC-8); its role objects are then not read and stage 2's strict role check fails its workflow.
  Mitigation: stage 2 is delivered after part 1 is merged, or the consumer converts the access
  package once part 1 lands; stated in the docs. Likelihood high if the order slips; impact: the
  consumer's run fails with a clear message.
- **RISK-4**: the stage-1 reader change (new required columns) refuses a hand-built test `.qea`
  lacking them; only the builder is affected, which this change updates.

## Delivery decisions

- **D-1 Parallel stages (lead, 2026-11-21).** The owner asked to advance in parallel. The tasks of
  each stage chain (1.1 → 1.4, 2.1 → 2.4) and stage 2's reader edits the files of 1.1, so stage 2
  starts in its own worktree as soon as 1.1 is committed, branched from it; 2.1 runs while 1.2–1.4
  run, and stage 2 rebases onto develop after stage 1 merges (P-0002, P-0003 for generated files).
  DEC-7 (stage 1 does not wait for stage 2) holds; only stage 2's start moves earlier.
- **D-2 Review set.** MEDIUM, no `RISK-` row names a stage's files as risky: per P-0005 one L2 and
  one L3 pass per stage, the full review (L1, L2, L3, L4 with L5) once at the end of stage 2. No
  tester: the PLAN has no `## Invariants` section and the appetite is below LARGE.
- **D-4 RunState outside the blocks (task 1.1 → 1.2).** The reader copies the `@VAR` blocks into
  `run_values` and drops the rest, but PD-3 makes non-blank text outside the blocks a problem.
  `UmlObject` gains `run_state_rest` (the text outside the blocks, stripped; absent when blank),
  filled by the reader; the role rule (1.2) judges it. The record stays a copy of the file.
- **D-5 A state node's raw kind (task 2.1 → 2.2).** PD-2's `node_kind` (`state`, `initial`)
  cannot carry the NType PD-5 step 2 must name ("StateNode kind <NType>"). `UmlStateNode` gains
  `node_type` (the raw `NType`, StateNode rows only); `node_kind` is absent for a StateNode that
  is not Initial, and the workflow rule (2.2) reports it as `no_rule` with `node_type`. The reader
  judges no kind. Also as built: `UmlStateFlow.uml_tagged_values` reuses `UmlTaggedValue` (owner =
  connector id); `UmlStatechart.node_ids` holds only state nodes of the converted subtree.
- **D-6 The refusal message (task 1.3).** `StagedFileRefused` carries the loader's message as is,
  which names the staged file's temporary path; PD-4 promises "the loader message", and the case
  only arises when a conversion rule missed something. The exception keeps PD-4's name without an
  `Error` suffix (`noqa: N818`).
- **D-7 Diagrams in Mermaid (task 1.4).** PD-7 says PlantUML, but the docs build renders only
  `[mermaid]` blocks (`make check-diagrams`). A role definition is drawn as a `classDiagram` box
  named `<object> : rp:RoleDefinition` with its run-state values as rows (Mermaid has no object
  diagram); stage 2's state diagram uses `stateDiagram-v2`.
- **D-8 The real-model run (task 1.4).** The run on the first consumer's model, its access package
  now converted, stops at one `no_rule` of the model itself (a boundary in the access package with
  no root), before any role is written. Its three role Objects are well-formed (read-only query).
  The converter is not changed for it: the consumer fixes its model, and the counts in
  `evidence/real-model-run.md` are filled from the next run (stage 2's 2.4 run repeats it).
- **D-9 Stage 1 review (L2+L3, one pass): no Critical finding.** W1 (gate evidence) is answered by
  a logged `make refresh-map` on HEAD `919aa2be` (exit 0, 0 unmapped) and the PR body's corrected
  gate line. Under the floor, carried to the full review at the end of stage 2:
  - W2: no test for a `Note=` key in a `@VAR` block, for a stray `<root>.roles.yaml` with the
    run's own root name, or for a block with no `Variable`.
  - W3: the scenario "an object of another class" is mapped at requirement level only.
  - S1: task 1.1 regenerated the stale library file `rp_persistence_rows.py` (develop's freshness
    check let it through); named in the PR body.
  - S2: `write`'s docstring narrows PD-8's path to a top-level name; stage 2 (2.3) widens it.
  - S3: an Object classified by a class the reader did not read is named by EA's numeric id.
  - S4: the conventions page copies the levels and actions the library defines.
- **D-10 Full review, accepted (one fix pass).** Re-labelled Critical by the lead, each with its
  reason:
  - C1 (L4 W1, L4 W6, L3 S3): the workflow rule builds transitions and the workflow as bare
    dicts and both serialisers copy the field lists by hand, though the library's generated
    `Workflow`, `WorkflowTransition` and `RoleDefinition` exist. Reason: hard rule P-0007 and
    AGENTS.md principle 2. Fix: build the generated models and write both files from
    `model_dump(mode="json", exclude_defaults=True)` through one YAML helper, keeping the
    files byte for byte as PD-6 states (key order, `comment_required` only when true).
  - C2 (L2 W3): the reader selects Statechart diagrams by the diagram's package, but the
    signed-off requirement reads "each Statechart diagram whose nodes are in the converted
    packages"; an empty or foreign placeholder diagram in a converted package fails the run.
    Reason: divergence from a signed-off requirement. Fix: a Statechart diagram is a workflow
    when it holds at least one state node of the converted packages, wherever the diagram sits;
    one holding none is not read. Tests: an empty Statechart in a converted package converts as
    before; a diagram in an excluded package showing converted states is read.
  - C3 (L2 W2): the conventions page names `workflow_transition` for a StateFlow with a name or
    a guard, which the reader refuses as `no_rule` (PD-1). Reason: it misleads the modeller and
    the page is edited for C2 anyway. Fix: the page's "What fails" rows and the design's error
    matrix row say `no_rule`.
- **D-11 Full review, under the floor** (no fix in this EPIC; follow-up candidates):
  - L1 W1: `write` does not refuse a `files` key that leaves `--out` (safe today: names come
    from the validated `workflow_name` and the NCName `--root-name`). L1 S1: element names go
    unescaped into the tab-separated report.
  - L1 S2: the library's `load_role_definitions` reads in the locale's encoding and lets
    `UnicodeDecodeError` through; a library defect, filed as an issue of this repository, not
    worked around in the converter.
  - L4 W2 (two copies of the `ValidationError` formatting; no truncation), W3 / L3 S2 (one
    constant for the output folder and the derived IRI segment), W4 (a refused role also makes
    its transitions report "not drawn"), W5 (overloaded `drawn` names), S1–S8.
  - L3 S1 (the writer infers each file's kind from its name).
  - L2 W1 (gate evidence): answered by a logged `make refresh-map` on the PR's head. L2 W4 and
    D-9 W3 (scenarios mapped at requirement level only, since a row is per test id). L2 S1,
    S2 (spec wording of "a drawn workflow"), S3 (two untested messages), S4 (tagged values on a
    State are neither read nor refused).
  - D-9's stage-1 items stay under the floor; none was re-labelled.
- **D-12 For the developer.** (a) L3 W1: PD-4 runs only the per-file loaders, so the library's
  whole-model checks at service start (`Workflows._check`, `_by_class`) never run on the
  converter's output; recommended: also run them in `write` when a workflow is drawn, which
  changes PD-4. Kept as decided until the developer says otherwise. (b) L2 W5: no roles or
  workflow file has yet been written from the consumer's model (D-8); the EPIC merges with that
  open, and the rerun after the consumer's boundary fix is in the hand-over.
- **D-12 answered (developer, 2026-11-21).** (a) A follow-up issue adds the library's whole-model
  workflow check to `write`; PD-4 stands for this EPIC. (b) Both stages merge now; the
  real-model rerun is an open item of the hand-over.
- **D-13 The how-to page (cold reader, developer: fix now).** The cold reader could not follow
  `howto/uml-to-linkml.adoc` from roles and workflows to a running service: RISK-3's note says
  both "together" and "first", and no example goes from `rp-uml2linkml` to a full
  `install_service(...)` call. One docs fixer: the note says one run whose `--package` holds both
  the roles' and the workflows' packages; an end-to-end example (command, files written,
  `rp-generate`, the `install_service` call with its import, and the order); then the full gates
  once (`make check-all`, `check-diagrams`).
- **D-14 Nesting and `member_class` (developer).** Beside this EPIC: a reference collection's
  `dct:hasPart` role to its own class should also fix `member_class` to that class, as the
  toolkit's `ReferenceCollection` description says; a follow-up issue (#241's converter).
- **D-3 Part 1 landed.** #245 part 1 (`module_kind`) merged in #247 before stage 1, so RISK-3's
  order holds and the consumer may convert its access package.
