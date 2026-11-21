<!-- Parents: issue #245, parts 2 and 3 (inputs/seed.md); openspec/specs/rp-uml-import ("The toolkit
     is reused, not redefined"); rp-access (role definitions), rp-workflow (the workflow file).
     Depends on: uml-to-linkml (archived 2026-11-21), whose reader and rules this extends.
     Part 1 of #245 (`module_kind` per package) is fixed separately and is not in this EPIC.
     Serves: MWB2 v2-02-model-from-ea, phase B (D-12): its hand-written roles and workflow files.
     Seeds: inputs/seed.md, inputs/qa.md (owner's round of 2026-11-21), inputs/probe.md. -->

# EPIC: Role definitions and workflows drawn in UML

## Appetite

**MEDIUM, two stages.** One new capability of the converter: two new element rules in the existing
reader and converter, and two new output files in toolkit formats. Stage 1 roles, stage 2
workflows. No library change.

## Why

A model drawn in Enterprise Architect still needs two hand-written files beside it: the role
definitions `install_service(rules=...)` reads and the workflow files `load_workflow` reads. They are
the toolkit's own concepts, so leaving them out of the drawing splits one model across two sources.
Today the converter even fails on a model that draws them (an Object, a State or a StateNode in a
converted package has no rule). The first consumer has drawn both (inputs/probe.md) and keeps its
hand-written files until this lands.

## Solution outline

- **Stage 1, roles.** An EA Object whose classifier is the drawn toolkit class `rp:RoleDefinition`
  is a role definition; its run-state values `role`, `level` and `actions` (comma-separated) are its
  fields. The converter checks `level` against `RoleLevel` and each action against `Action`, read
  from the toolkit's metamodel, and writes `<root-name>.roles.yaml` in the format
  `install_service(rules=...)` loads, one report line per role. An Object of any other classifier
  still fails the run.
- **Stage 2, workflows.** Each Statechart diagram whose nodes are in the converted packages is one
  workflow. Its `State` elements are the workflow's states. The one transition leaving its Initial
  node marks the initial state. Every other `StateFlow` is a transition, with tagged values
  `roles=<role>[,<role>…]` and `comment_required=true|false`. The converter writes
  `workflows/<name>.workflow.yaml` in the format `load_workflow` reads, with the IRI the diagram's
  name gives (DEC-4). It checks that the `workflow` tag of every class names a drawn workflow, and
  that every role of a transition is a drawn role definition.

Every check failure fails the run, naming the element, and nothing is written (the converter's
rule). A model that draws none of these converts exactly as today.

## Key decisions

- **DEC-1:** a role definition is an EA Object classified by the drawn `rp:RoleDefinition`. Its
  fields are run-state values, `actions` comma-separated. The file is `<root-name>.roles.yaml`
  beside the schemas. Source: issue #245 part 2, confirmed by the probe.
- **DEC-2:** one Statechart diagram is one workflow; a state or Initial node on two Statechart
  diagrams fails the run. Source: owner, Q-1. Rejected: a StateMachine element owning the states
  (the consumer would redraw); both encodings (two readers).
- **DEC-3:** the workflow's name is the local part of the diagram's name, and a class's `workflow`
  tag must name a drawn workflow. The «workflow states» enumeration stays a not-generated drawing aid
  (R-30) and is not compared with the states.
- **DEC-4:** the workflow's IRI comes from the EA model: a diagram named `pfx:local` gives the
  expansion through the prefixes file, as every other element name does. A plain name falls back to
  `schema_base` + `workflows/<name>`, with a `derived-iri` report line flagging the model as
  incomplete. Source: owner, Q-2 ("the EA must give IRIs otherwise the model is wrong"; option 1 as
  the backup), planner's reading in inputs/qa.md.
- **DEC-5:** strict roles: every role a transition names must be a drawn role definition, otherwise
  the run fails naming the transition. A model that draws workflows draws its roles. Source: owner,
  Q-3.
- **DEC-6:** a construct with no rule fails the run, naming it: a final, choice, junction, fork or
  history node; a guard or name on a StateFlow; a StateMachine element; an Object of another
  classifier; a run-state variable other than the three. Source: owner, Q-4.
- **DEC-7:** two stages, one PR each; stage 1 does not wait for stage 2. Source: owner's brief.
- **DEC-8:** `module_kind` (part 1 of #245) is not in this EPIC. Role objects drawn in a package the
  consumer excludes today are converted once that package is converted. Source: owner's brief.

## Rabbit-holes

- **The reader's schema check.** `qea.py` checks up front that the tables and columns it reads exist.
  Adding `t_object.Classifier`, `RunState`, `NType`, `t_diagram`, `t_diagramobjects` (already read
  for boundaries) and `t_connectortag` must not refuse a real `.qea` that has no state machines; the
  test builder (`QeaBuilder`) gains the columns and the table.
- **NType values.** Only `NType=3` (Initial) is seen in a real model. Every other StateNode fails
  (DEC-6), so the PLAN does not guess the other codes.
- **Names.** A workflow name must match `^[a-z][a-z0-9-]*$` and a state `^[a-z][a-z0-9_-]*$`; EA
  names are used as drawn and checked, never rewritten into snake case.
- **Byte-identical reruns.** Roles in a stable order, states and transitions in a stable order (by
  name, not by EA id), as the converter's existing output.

## No-gos

- No `module_kind` (part 1). No StateMachine elements, composite or nested states, final states,
  guards, entry or exit actions.
- No change to the toolkit's role or workflow formats, loaders or enums.
- No reading of the consumer's own `Action` enumeration; actions are the toolkit's.
- No XMI. No writing back into the `.qea`.
- No check of the «workflow states» enumeration against the states.

---

## What Changes

- `rp-uml2linkml` reads Objects classified by `rp:RoleDefinition`, Statechart diagrams with their
  State and Initial nodes, and `StateFlow` connectors with their tags.
- New output files: `<root-name>.roles.yaml` and `workflows/<name>.workflow.yaml`; new report
  kinds (`role`, `workflow`, `derived-iri`).
- Generated working records (`rp_generation.yaml`): the UML records for objects, states and
  transitions.
- Docs: the UML conventions page (P-0014) and the how-to.

## Capabilities

### Modified Capabilities

- `rp-uml-import`: role definitions and workflows drawn in UML convert to the toolkit's role and
  workflow files.

## Impact

`rdf_persistence_generation/uml/` (`qea.py`, `convert.py`, `write.py`, `cli.py`; new `roles.py`,
`workflows.py` and `dump.py`), `rdf_persistence_generation/model/rp_generation.yaml` and its
generated module, `tests/generator/` (`uml_qea.py` builder, `uml_model.py`), docs
`reference/uml-conventions.adoc`, `howto/uml-to-linkml.adoc`. Not breaking for the command line: a
model without these elements converts and reports as before; one that has them used to fail.
`convert` now returns a fourth value, the files it draws (PD-8); its only callers are the command
line and the tests.

## Delivery reconciliation

What was delivered against this shape (rule P-0004). The decisions are in
[design.md](design.md#delivery-decisions); this table only names them.

| Shaped | Delivered | Why | Decision | PR |
|---|---|---|---|---|
| Two stages, stage 2 after stage 1 | Stage 2 built in parallel from task 1.1, rebased onto each stage-1 commit; stage 1 merged first | The developer asked to advance in parallel | D-1 | #257, #263 |
| `module_kind` out of this EPIC (DEC-8) | Delivered before it, separately | Its order mattered for RISK-3 | D-3 | #247 |
| The reader copies an Object's run state | It also keeps the text outside the `@VAR` blocks, which the role rule refuses | PD-3 makes that text a problem | D-4 | #257 |
| `node_kind` `state` or `initial` | Also the raw `node_type`, so the rule names an unknown StateNode kind | PD-5 must name the NType | D-5 | #263 |
| PlantUML snippets (PD-7) | Mermaid (`classDiagram`, `stateDiagram-v2`) | The docs build renders only Mermaid | D-7 | #257, #263 |
| A Statechart diagram by its package (as first built) | By its states: a diagram showing a converted state, wherever it sits | The signed-off requirement | D-10 C2 | #263 |
| Files written from hand-built mappings (as first built) | From the library's generated models through one `model_dump` helper; byte for byte as PD-6 | P-0007 | D-10 C1 | #263 |
| The how-to's `rules=`/`workflows=` lines (PD-7) | Also a step 5 "Start the service" with a full `install_service` call | A cold reader could not reach a running service | D-13, D-15 | #263 |
| The run on the consumer's model records counts (1.4, 2.4) | Recorded up to the model's own boundary problem; no file written from it yet | The consumer fixes its model; the developer accepted merging (D-12b) | D-8, D-12 | #257, #263 |

Not delivered: the real-model run that writes the files (open in the hand-over, after the
consumer's model fix). Follow-ups: #258 (the library's roles-file encoding), #259 (the library's
whole-model workflow check in `write`), #260 (a nesting role fixes `member_class`), #261 (the
service-start docs). The review's findings under the floor are in D-9 and D-11.
