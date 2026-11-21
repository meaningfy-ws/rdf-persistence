<!-- Secondary input, never groomed: read-only probe of a real EA model, 2026-11-21.
     Script: temp/uml-probe/roles_workflows.py (stdlib sqlite3, opened `mode=ro` on a copy).
     Counts and shapes only, no consumer names beyond the ones the issue already uses. -->

# Probe: where EA keeps role objects and state machines

Two copies of the first consumer's model were probed. The one on its default branch draws neither
construct (no Object, State, StateNode or StateFlow rows, no Statechart diagram). The copy on its
modelling branch (EA round 23, commit of 2026-11-21, "access and workflows in EA") draws both; the
table below is that copy.

| Question | Evidence |
|---|---|
| How is a role definition stored? | `t_object` rows with `Object_Type='Object'` (3), each with `Classifier` = the `Object_ID` of a Class named `rp:RoleDefinition` drawn in the same package (no attributes, a note). `Classifier_guid` NULL, `ParentID` 0, no tags, no `t_xref`. |
| Where are its fields? | `t_object.RunState`, one string: `@VAR;Variable=role;Value=owner;Op==;@ENDVAR;@VAR;Variable=level;Value=tenant;Op==;@ENDVAR;@VAR;Variable=actions;Value=read,modify,delete,administer;Op==;@ENDVAR;`. Variables seen: `role`, `level`, `actions` only. `actions` is one comma-separated value. |
| Is there a StateMachine element? | **No.** States are `Object_Type='State'` (5), the initial node `Object_Type='StateNode'` with `NType=3` (1); all have `ParentID=0`, `Classifier=0`, no stereotype, tags or PDATA. No other NType is present (a final node's code is not seen). |
| What groups the states into one workflow? | Only a diagram: `t_diagram.Diagram_Type='Statechart'` (1), in the package that holds the states. Its 6 nodes are listed in `t_diagramobjects`; no state is on two diagrams. The diagram's name equals the `workflow` tagged value of the one class tagged so (a plain name, not a CURIE). |
| How are transitions stored? | `t_connector` rows with `Connector_Type='StateFlow'` (9), `Direction='Source -> Destination'`, empty `Name`, NULL `PDATA*` (no guard). |
| Where are a transition's tags? | `t_connectortag` (`ElementID` = `Connector_ID`, `Property`, `VALUE`): `roles` (comma-separated role names) and `comment_required` (`true`/`false`) on 8 of 9. The one without tags is the transition leaving the Initial node. |
| What does the converter do with them today? | It fails: `qea.py` reads only `Class`/`Enumeration` (+ ignored `Package`, `Note`, `Text`, `Boundary`), so each Object, State and StateNode in the converted subtree is a `no_rule` problem. It does not read `Classifier`, `RunState`, `NType`, `t_connectortag`. A drawn toolkit class such as `rp:RoleDefinition` is already "not generated" (R-28). |
| The «workflow states» enumeration | Present on the default-branch copy (5 literals), removed on the modelling branch. Already a not-generated stereotype (R-30). |
| Toolkit facts the output must meet | `RoleLevel`: `system, tenant, aggregate`; `Action`: `read, modify, delete, administer, annotate` (`rp_access.yaml`). The consumer's own `Action` enumeration has values the toolkit lacks (`comment`, `transition`); the probed role objects use only toolkit actions. Workflow `id`: absolute IRI, no trailing `/` or `#`; `workflow_name`: `^[a-z][a-z0-9-]*$`; state: `^[a-z][a-z0-9_-]*$` (`rp_workflow.yaml`, `rp_core.yaml`). |
