<!-- Secondary input, never groomed: GitHub issue #245 (meaningfy-ws/rdf-persistence), fetched 2026-11-21. The EPIC (../proposal.md) supersedes it. -->

# #245 rp-uml2linkml: access modules, role definitions and workflows drawn in UML

## Summary

Let an application draw its **access model, role definitions and workflows in UML**, extending the toolkit's concepts, and have `rp-uml2linkml` write what the toolkit loads for them. Today the converter writes every package as `module_kind: domain`, and role definitions and workflows (data the service loads from files: `RoleDefinition`, `Workflow`/`WorkflowTransition`) cannot be drawn at all, so they stay hand-written beside a model that is otherwise drawn.

## Context

Consumer: MWB2, change `v2-02-model-from-ea`, phase B, rdf-persistence lock `030f580f` (v0.8.0). The developer's requirement (2026-11-21): access and the workflows with their state transitions are modelled in the UML model, on top of (subclassing) the toolkit's concepts, like the rest of the domain. MWB2 keeps its hand-written access module, roles file and workflow file until this lands.

## What is missing

1. **A package as an access (or other non-domain) module.** The converter annotates every module `module_kind: domain`. An access package (a subclass of `TenantAccess`, drawn as a generalisation to the toolkit's class, which already converts to `is_a`) must be `module_kind: access`, so `rp-generate`'s boundary rule keeps domain modules from importing it.
2. **Role definitions drawn in UML.** The toolkit's roles are data (`RoleDefinition`: `role`, `level`, `actions`), passed to `install_service(rules=<file>)`. There is no UML convention for them.
3. **Workflows drawn in UML.** A workflow is data (`Workflow`: name, states, initial state, transitions with roles and `comment_required`), passed as `workflows=[<file>]`, and a class names it with the `workflow` tagged value (which already adds `UnderWorkflow`). There is no UML convention for its states and transitions; the states are drawn today as an enumeration stereotyped «workflow states», not generated.

## Proposed capability

1. **Package tagged value `module_kind`** (`domain` default; `access`, …: the metamodel's values), written as the module's annotation. A value the metamodel does not know fails the run.
2. **Role definitions as instance specifications** of the toolkit's class: an EA `Object` whose classifier is the drawn `rp:RoleDefinition`, with run-state values `role`, `level`, `actions` (comma-separated `Action` values), in the converted package. The converter writes `<root-name>.roles.yaml` (the format `install_service(rules=...)` reads) and reports each role. A value outside `RoleLevel`/`Action` fails the run.
3. **Workflows as UML state machines** owned by the class under workflow (or named by its `workflow` tag): `State` elements are the states (their names in snake case, checked against the workflow state pattern), the `Initial` pseudostate's transition marks `initial_state`, each `StateFlow` transition is a `WorkflowTransition` with tagged values `roles=<role>[,<role>…]` and `comment_required=true|false`. The converter writes `workflows/<name>.workflow.yaml` (the format `load_workflow` reads) and the class's `workflow` annotation. A transition naming a role that is not defined, or a state machine with no initial state, fails the run. The «workflow states» enumeration stays a not-generated drawing aid, or is checked to equal the state machine's states.

```text
lib:Loan «root», workflow=loan
state machine "loan": [*] --> requested; requested --> approved {roles=librarian}; requested --> refused {roles=librarian, comment_required=true}
Object "librarian" : rp:RoleDefinition  {role=librarian, level=tenant, actions=read,modify,transition}
package lib/access  {module_kind=access}
  lib:LibraryAccess --|> rp:TenantAccess
```

writes `library_access.yaml` (`module_kind: access`, `LibraryAccess is_a TenantAccess`), `library.roles.yaml`, `workflows/loan.workflow.yaml`.

## Why it belongs in rdf-persistence

Any application whose model is drawn in UML has roles and workflows; they are the toolkit's concepts, and their file formats are the toolkit's. Leaving them hand-written splits one model across two sources.

## Acceptance

- **Given** a package tagged `module_kind=access` with a class generalising `rp:TenantAccess` **When** converted **Then** its module is annotated `module_kind: access`, the class is `is_a: TenantAccess`, and `rp-generate`'s boundary rule passes for a root that imports it.
- **Given** three `rp:RoleDefinition` objects **When** converted **Then** the roles file holds the three and `install_service(rules=<file>)` accepts it; an object with `level=planet` fails the run naming the object.
- **Given** a state machine with an initial state, four states and five transitions on a class tagged `workflow=loan` **When** converted **Then** `load_workflow` reads the written file with those states and transitions, and a transition naming an unknown role fails the run naming the transition.
- **Given** a model with none of these **When** converted **Then** nothing changes from today.

## Impact on the consumer

MWB2 keeps `models/access.yaml`, `models/mwb2_roles.yaml` and `models/workflows/conceptual-mapping.workflow.yaml` hand-written (and its EA `access` package excluded from conversion) until this is merged; the rest of the change goes on.

