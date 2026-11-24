# rp-uml-import Specification

## Purpose
Turning a UML class model drawn in Enterprise Architect into toolkit-conformant LinkML, so a team
that models in UML gets the LinkML the generator needs without writing it by hand. `rp-uml2linkml`
reads the `.qea` file read-only, follows the model2owl UML conventions and the toolkit's own (the
UML conventions page), reuses the toolkit's classes, slots and annotations, and fails the run,
naming every element no rule maps, rather than guess.

## Requirements

### Requirement: A UML class model converts to toolkit-conformant LinkML

`rp-uml2linkml` SHALL read an Enterprise Architect `.qea` file read-only and write one LinkML
module per UML package, the packages of an import cycle together as one module, and a root schema
importing them. A module is `module_kind: domain` unless its package's `module_kind` tagged value
names another kind of the metamodel's `ModuleKind`; any other value fails the run. When every class, slot and enumeration of the model
carries a note, `rp-generate`'s lint and boundary check pass on the output unchanged; an element
without a note gets no placeholder description, and the report lists it. A slot used in several
packages is defined once, in the module the others reach by imports, and fails the run when there is
none. A class or an enumeration whose stereotype is listed as not generated produces nothing, and
the report names it. A link to such a class becomes a `range: uri` slot with no line of its own; a
dependency to such an enumeration, or an attribute typed by one, gets a `not-generated` line and no
slot. A connector with a note, text, boundary or package at an
end is not read. The model follows the model2owl UML conventions; the toolkit's own conventions are
stated on the UML conventions page.

#### Scenario: a package with a root and a part
- **GIVEN** a `.qea` with a package holding classes, attributes, associations, generalisations, an
  enumeration linked by a dependency, and a «root» class in a boundary with a part, every element
  with a note
- **WHEN** `rp-uml2linkml` runs
- **THEN** it writes one module per package with the URIs, cardinalities, descriptions, the
  `AggregateRoot` mixin with `rp_path`, and the `owned` slots, and `rp-generate`'s lint and
  boundary check accept it

#### Scenario: an access package
- **GIVEN** a package tagged `module_kind=access` whose class generalises `rp:TenantAccess`
- **WHEN** it is converted
- **THEN** its module is annotated `module_kind: access`, the class is `is_a: TenantAccess`, and
  `rp-generate`'s boundary rule passes for the root that imports it; a value such as `planet`
  fails the run naming the package

#### Scenario: packages that refer to each other
- **GIVEN** two packages whose classes refer to each other
- **WHEN** they are converted
- **THEN** both are written as one module, named after the first package in path order, and the
  report has a `merged-cycle` line naming both packages

#### Scenario: an element without a note
- **GIVEN** a class with no note
- **WHEN** it is converted
- **THEN** it has no description, and the report has a `no-note` line naming it

#### Scenario: multiplicity
- **GIVEN** attributes and association ends with the multiplicities `0..1`, `1..1`, `1..*`, `2..5`
  and none
- **WHEN** they are converted
- **THEN** `required` follows a lower bound of at least one, `multivalued` an upper bound above one,
  `2..5` gives `minimum_cardinality: 2` and `maximum_cardinality: 5`, and a missing multiplicity is
  read as `0..*` with an `unspecified-multiplicity` report line

#### Scenario: an enumeration with no literals
- **GIVEN** an enumeration with no literals, the range of a dependency
- **WHEN** it is converted
- **THEN** the slot ranges over `uri`, and the report has an `external-list` line naming the
  enumeration

#### Scenario: a language string
- **GIVEN** an attribute typed `rdf:langString`
- **WHEN** it is converted, while the toolkit has no language-string range
- **THEN** the run fails naming the attribute, and the attribute is never turned into a plain string

#### Scenario: a connector's direction
- **GIVEN** an association whose direction is neither `Source -> Destination` nor `Bi-Directional`,
  or a `Source -> Destination` association that also names a source role
- **WHEN** it is converted
- **THEN** the run fails naming the connector and its direction

#### Scenario: an abstract class drawn with a stereotype
- **GIVEN** a class stereotyped «Abstract»
- **WHEN** it is converted
- **THEN** the class is `abstract: true`

#### Scenario: an element no rule maps
- **GIVEN** a model with an association class
- **WHEN** it is converted
- **THEN** the command fails naming the element and the missing rule, and writes nothing

#### Scenario: stable output
- **GIVEN** a converted schema and an unchanged model
- **WHEN** it is converted again
- **THEN** the output is byte-identical

### Requirement: The toolkit is reused, not redefined

The converter SHALL map toolkit concepts to the toolkit's own classes, slots and annotations: default
mixins on roots and labelled parts, `rp_mixins` and drawn generalisations to toolkit classes, slots
whose IRI is a toolkit slot's `slot_uri` (except `id`), and every class tagged value named like a
toolkit class annotation. A «tenant root» becomes the class of the tenant's meta graph, not an
aggregate root; an abstract class whose concrete descendants are all roots, and which a slot ranges
over, becomes an aggregate root. A reference collection's `dct:hasPart` role to another converted
class fixes the collection's `member_class` to that class. A reference collection whose only
`dct:hasPart` role to a converted class points at its own class SHALL have its own class as its
`member_class` (a collection of collections); beside a role to another class, or when a collection
above or below it in the class hierarchy fixes a member class, a role to its own class stays
nesting.

#### Scenario: a reference collection's member class
- **GIVEN** `«root» lib:Shelf` tagged `rp_mixins=ReferenceCollection` (or generalising a class that
  is) with a `dct:hasPart` role to `«root» lib:Book`
- **WHEN** it is converted
- **THEN** `Shelf` has `slot_usage: {member_class: {equals_string: Book}}`, a `Shelf` of another
  member class is refused by its model and its shape, and the report has no `toolkit-slot-kept`
  line for the role; a role to `Shelf` itself beside it (nesting) stays the toolkit's `has_part`,
  reported as before, and roles to two different classes fail the run naming `Shelf`

#### Scenario: a collection of collections
- **GIVEN** `«root» lib:Shelf` tagged `rp_mixins=ReferenceCollection` whose only `dct:hasPart` role
  points at `Shelf`
- **WHEN** it is converted
- **THEN** `Shelf` has `slot_usage: {member_class: {equals_string: Shelf}}`, and the report has no
  `toolkit-slot-kept` line for the role

#### Scenario: a role to its own class in a collection hierarchy
- **GIVEN** an abstract `lib:Folder` tagged `rp_mixins=ReferenceCollection` whose only `dct:hasPart`
  role points at `Folder`, and `«root» lib:Album` generalising it with a `dct:hasPart` role to
  `«root» lib:Photo`
- **WHEN** it is converted
- **THEN** `Album` fixes `member_class` to `Photo`, `Folder` fixes none and its role stays the
  toolkit's `has_part`, reported as `toolkit-slot-kept`, and the run has no problem; likewise a
  subclass's lone role to its own class under a parent that fixes a member class stays nesting

#### Scenario: an abstract collection narrowed by its subclasses
- **GIVEN** an abstract `lib:Collection` tagged `rp_mixins=ReferenceCollection` with a `dct:hasPart`
  role to an abstract `lib:Resource`, and `«root» lib:Shelf` generalising it with its own
  `dct:hasPart` role to `«root» lib:Book`, which generalises `Resource`
- **WHEN** it is converted and generated
- **THEN** `Shelf` fixes `member_class` to `Book`, `Collection` fixes none and its role is reported
  as `toolkit-slot-kept` with its range, and the generated code passes the type check; when no
  subclass draws its own role, `Collection` keeps `Resource`; a subclass role to a class that does
  not descend from `Resource` fails the run naming `Shelf`, its class, `Collection` and `Resource`

#### Scenario: a root that is an activity
- **GIVEN** `«root» lib:Loan` tagged `rp_mixins=Activity` with `prov:startedAtTime [1..1]` and `rp_path=loans`
- **WHEN** it is converted
- **THEN** `Loan` is `is_a: Activity`, mixes in `AggregateRoot`, `Described` and `Tracked`, has
  `annotations: {rp_path: loans}`, defines no new slot and narrows no toolkit-filled slot (the
  `[1..1]` on `started_at_time` is dropped), and the report names `started_at_time`

#### Scenario: a tenant root
- **GIVEN** a class `lib:Library` stereotyped «tenant root»
- **WHEN** it is converted
- **THEN** it carries `annotations: {graph: meta}`, does not mix in `AggregateRoot`, and has no
  `rp_path`

#### Scenario: an abstract root
- **GIVEN** an abstract class `lib:Item` whose concrete subclasses are all «root», and a slot whose
  range is `Item`
- **WHEN** it is converted
- **THEN** `Item` mixes in `AggregateRoot` with no `rp_path`, and each subclass still lists
  `AggregateRoot`

#### Scenario: a tagged value becomes an annotation
- **GIVEN** a class tagged `rp_writes=service`
- **WHEN** it is converted
- **THEN** it carries `annotations: {rp_writes: service}`, and a value outside `WritesKind` fails the run

#### Scenario: a business identifier
- **GIVEN** `lib:Book` with `dct:identifier : xsd:string [1..1]`
- **WHEN** it is converted
- **THEN** it has a required string slot `identifier` (`slot_uri: dcterms:identifier`) and keeps `id` as its IRI

#### Scenario: an excluded package
- **GIVEN** `--exclude-package circulation` and an association `lib:Book → circulation:Loan`
- **WHEN** the model is converted
- **THEN** no slot is produced and the report names the association

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
converted as before, unchecked. When the run draws a workflow, the workflow files and the roles file
it writes SHALL also pass, against the schema it writes, the check the service runs on them at
start; a refusal SHALL fail the run with exit 1, naming the classes and workflows it concerns and
any file by its path under `--out`, and nothing SHALL be written.

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

#### Scenario: a workflow the service would refuse
- **GIVEN** workflow and roles files that each load alone, and a schema in which two classes with
  one class IRI name different workflows
- **WHEN** they are written
- **THEN** the run exits 1 naming the second class, the shared IRI and both workflows, no message names a staging path,
  and `--out` is unchanged

### Requirement: A model without roles or workflows converts as before

A model that draws no role definition object and no Statechart diagram SHALL convert to the same
files, byte for byte, as before this change, and no roles or workflow file SHALL be written.

#### Scenario: nothing drawn
- **GIVEN** a model with neither
- **WHEN** it is converted
- **THEN** the output equals the output before this change

### Requirement: A subclass that narrows an inherited role keeps the narrowed multiplicity

When a class redraws an inherited association role with other multiplicity limits than its
ancestor's, the converter SHALL write each differing `required` and `multivalued` limit into that
class's `slot_usage`, `false` included, so that the class's induced slot has the redrawn limits.

#### Scenario: an inherited 0..* role narrowed to 1
- **GIVEN** an abstract class `A` with a role `p 0..*` to `V`, and a «root» class `B` generalising `A` that redraws `p 1` to `W`, a subclass of `V`, with `unique_key = k: p`
- **WHEN** the model is converted and generated
- **THEN** `B.slot_usage.p` has `range: W`, `required: true` and `multivalued: false`, and the key `k` is accepted

#### Scenario: an inherited required role made optional
- **GIVEN** `A` with a role `p 1..1`, and `B` generalising `A` that redraws `p 0..1`
- **WHEN** the model is converted
- **THEN** `B.slot_usage.p` has `required: false`

#### Scenario: agreeing usages write no limit
- **GIVEN** every usage of a slot is single-valued
- **WHEN** the model is converted
- **THEN** no `multivalued` is written for it

### Requirement: The model is read without change and the output is written whole or visibly not

`rp-uml2linkml` SHALL read the `.qea` file without creating, changing or leaving any file beside it,
and without running code the file holds; a view, trigger or index named like a table it reads SHALL
be refused as a missing table. A path that names no file, a file that cannot be read, a file that is
not SQLite, and any error while reading SHALL each be one `rp-uml2linkml:` line saying which, with
exit 2, never a traceback. It SHALL stage its output inside `--out` and move the report into
`--out` last, after removing the previous run's report, so a write that fails leaves no report in
`--out`. A folder or disk error while writing SHALL be one `rp-uml2linkml: cannot write <path>:
<reason>` line with exit 2. A staging folder left by an interrupted run SHALL be reported as a
`stale-file` line and not deleted.

#### Scenario: a missing model file
- **GIVEN** a `.qea` path that names no file
- **WHEN** `rp-uml2linkml` runs
- **THEN** it exits 2 with `rp-uml2linkml: <path>: no such file`, and writes nothing

#### Scenario: a read error
- **GIVEN** a file with the SQLite header whose pages are corrupt
- **WHEN** `rp-uml2linkml` runs
- **THEN** it exits 2 with one `rp-uml2linkml: <path> cannot be read: <error>` line, and no traceback

#### Scenario: no side files
- **GIVEN** a `.qea` in WAL mode with no `-wal` file beside it
- **WHEN** it is converted
- **THEN** the folder of the `.qea` holds the same files after the run as before

#### Scenario: a view in place of a table
- **GIVEN** a file in which `t_object` is a view
- **WHEN** `rp-uml2linkml` runs
- **THEN** it exits 2 with `rp-uml2linkml: <path> has no table t_object`

#### Scenario: an interrupted write
- **GIVEN** an `--out` holding a previous run's files and report, and a move that fails with a disk
  error
- **WHEN** `rp-uml2linkml` runs
- **THEN** it exits 2 naming the file it could not write, `--out` holds no report, and a second run
  without the error writes the same files and the report

#### Scenario: an output folder that cannot be written
- **GIVEN** an `--out` that is a file
- **WHEN** `rp-uml2linkml` runs
- **THEN** it exits 2 with `rp-uml2linkml: cannot write <out>: <reason>`
