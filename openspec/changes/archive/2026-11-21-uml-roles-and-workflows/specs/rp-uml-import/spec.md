## ADDED Requirements

### Requirement: Role definitions drawn in UML convert to the roles file

`rp-uml2linkml` SHALL read each EA Object in the converted packages whose classifier is the drawn
toolkit class `rp:RoleDefinition` as one role definition, its run-state values `role`, `level` and
`actions` (comma-separated) as its fields, and SHALL write them to `<root-name>.roles.yaml` in the
format `install_service(rules=...)` loads, each named by a report line. A level outside `RoleLevel`,
an action outside `Action`, a missing or unknown run-state variable, or two definitions with one
level and role SHALL fail the run, naming the object, and nothing SHALL be written. An Object of any
other classifier SHALL fail the run as before.

#### Scenario: three roles
- **GIVEN** three `rp:RoleDefinition` objects with valid run-state values
- **WHEN** the model is converted
- **THEN** the roles file holds the three, and `load_role_definitions` reads it

#### Scenario: an unknown level
- **GIVEN** a role object with `level=planet`
- **WHEN** the model is converted
- **THEN** the run fails naming the object, and nothing is written

#### Scenario: an object of another class
- **GIVEN** an Object classified by a domain class
- **WHEN** the model is converted
- **THEN** the run fails naming the object

### Requirement: Workflows drawn as state machines convert to workflow files

`rp-uml2linkml` SHALL read each Statechart diagram whose nodes are in the converted packages as one
workflow: its `State` elements as the states, the target of the one transition leaving its Initial
node as the initial state, and every other `StateFlow` as a transition with the tagged values
`roles` (comma-separated) and `comment_required`. It SHALL write `workflows/<name>.workflow.yaml` in
the format `load_workflow` reads. The workflow's IRI SHALL be the expansion of a diagram named
`pfx:local`, whose local part is the name; a plain diagram name SHALL get `schema_base` +
`workflows/<name>` and a `derived-iri` report line. The run SHALL fail, naming the element, when a
diagram has no Initial node or more than one transition leaving it, a state is on two Statechart
diagrams, a transition names a role no drawn role definition defines or has no roles, a name breaks
the toolkit's name pattern, two diagrams give one workflow name or IRI, the converted packages hold
a Statechart diagram and a class's `workflow` tag names no converted workflow, or the diagram holds a
node, connector or value no rule converts (a substate, a final or other pseudostate, a guard, a
trigger, a state behaviour). With no Statechart diagram converted, a class's `workflow` tag SHALL be
converted as before, unchecked.

#### Scenario: a drawn workflow
- **GIVEN** a Statechart diagram `lib:loan` with an Initial node, four states and five tagged transitions, and a class tagged `workflow=loan`
- **WHEN** the model is converted
- **THEN** `load_workflow` reads the written file with those states, transitions and initial state, and the IRI `lib:loan` expands to

#### Scenario: a plain diagram name
- **GIVEN** the same diagram named `loan`
- **WHEN** the model is converted
- **THEN** the workflow's IRI is `schema_base` + `workflows/loan`, and the report has a `derived-iri` line for it

#### Scenario: an undefined role
- **GIVEN** a transition tagged `roles=archivist` and no role definition `archivist`
- **WHEN** the model is converted
- **THEN** the run fails naming the transition

#### Scenario: a final node
- **GIVEN** a Statechart diagram with a final node
- **WHEN** the model is converted
- **THEN** the run fails naming the node

### Requirement: A model without roles or workflows converts as before

A model that draws no role definition object and no Statechart diagram SHALL convert to the same
files, byte for byte, as before this change, and no roles or workflow file SHALL be written.

#### Scenario: nothing drawn
- **GIVEN** a model with neither
- **WHEN** it is converted
- **THEN** the output equals the output before this change
