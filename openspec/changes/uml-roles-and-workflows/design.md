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
| StateFlow | tag other than `roles`/`comment_required`, a name, PDATA set, `comment_required=yes` | problem naming the transition |
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
- **D-3 Part 1 landed.** #245 part 1 (`module_kind`) merged in #247 before stage 1, so RISK-3's
  order holds and the consumer may convert its access package.
