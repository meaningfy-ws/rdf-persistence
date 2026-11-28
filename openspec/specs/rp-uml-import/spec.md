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
module per UML package, packages whose classes refer to each other included (their modules import
each other), and a root schema importing them. A module is `module_kind: domain` unless its
package's `module_kind` tagged value names another kind of the metamodel's `ModuleKind`; any other
value fails the run. When every class, slot and enumeration of the model
carries a note, `rp-generate`'s lint and boundary check pass on the output unchanged; an element
without a note gets no placeholder description, and the report lists it. A slot used in several
packages is defined once, in the module the others reach by imports, and fails the run when there is
none. A class or an enumeration whose stereotype is listed as not generated produces nothing, and
the report names it. A link to such a class becomes a `range: uri` slot with no line of its own; a
dependency to such an enumeration, or an attribute typed by one, gets a `not-generated` line and no
slot. A connector with a note, text, boundary or package at an
end is not read. Which slots are owned SHALL come from compositions only; a boundary is an
annotation and its position, size and overlaps SHALL never be read. The model follows the model2owl
UML conventions; the toolkit's own conventions are stated on the UML conventions page.

#### Scenario: a package with a root and a part
- **GIVEN** a `.qea` with a package holding classes, attributes, associations, generalisations, an
  enumeration linked by a dependency, and `lib:Book` with a composition to its part `lib:Chapter`
  drawn beside the association `lib:hasChapter`, every element with a note
- **WHEN** `rp-uml2linkml` runs
- **THEN** it writes one module per package with the URIs, cardinalities, descriptions, the
  `AggregateRoot` mixin with `rp_path` on `Book`, and the `owned` slot `has_chapter`, and
  `rp-generate`'s lint and boundary check accept it

#### Scenario: a boundary moved in a layout pass
- **GIVEN** a converted model with a boundary around `Book` and `Chapter`
- **WHEN** the boundary is moved, shrunk off `Chapter` or slid off every class, and the model is
  converted again
- **THEN** the schemas are byte-identical to the first conversion

#### Scenario: an access package
- **GIVEN** a package tagged `module_kind=access` whose class generalises `rp:TenantAccess`
- **WHEN** it is converted
- **THEN** its module is annotated `module_kind: access`, the class is `is_a: TenantAccess`, and
  `rp-generate`'s boundary rule passes for the root that imports it; a value such as `planet`
  fails the run naming the package

#### Scenario: packages that refer to each other
- **GIVEN** two packages `books` and `shelves` whose classes refer to each other
- **WHEN** they are converted, and `rp-generate` runs on the output
- **THEN** each package is its own module (`app_books`, `app_shelves`), each importing the other,
  the report has no line about the cycle, and the generated package imports

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

#### Scenario: packages of different kinds that refer to each other
- **GIVEN** an access package and a domain package whose classes refer to each other
- **WHEN** they are converted, and `rp-generate` runs on the output
- **THEN** the conversion succeeds with one module per package, each with its own `module_kind`,
  and `rp-generate`'s boundary check refuses the domain module because it imports the access one

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
other classifier SHALL fail the run as before. A Realisation from an Object to a class SHALL be read
as the visible form of the Object's classifier and convert to nothing of its own; an Object with a
Realisation and no classifier SHALL take the Realisation's target as its classifier; a Realisation
to another class than the classifier, or Realisations to two classes, SHALL fail the run naming the
Object and both classes. A Realisation from anything but an Object SHALL fail the run as before.

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

#### Scenario: a role object that realises its class
- **GIVEN** a role object `librarian` classified by `rp:RoleDefinition` with a Realisation to
  `rp:RoleDefinition`
- **WHEN** the model is converted
- **THEN** the roles file is the one written without the Realisation, and the run has no problem

#### Scenario: a Realisation in place of the classifier
- **GIVEN** a role object with no classifier and a Realisation to `rp:RoleDefinition`
- **WHEN** the model is converted
- **THEN** it is read as a role definition, as with the classifier set

#### Scenario: a Realisation that disagrees with the classifier
- **GIVEN** a role object classified by `rp:RoleDefinition` with a Realisation to `lib:Book`
- **WHEN** the model is converted
- **THEN** the run fails naming the object, `RoleDefinition` and `Book`, and nothing is written

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

### Requirement: A redrawn role keeps its own cardinality bounds

When the usages of a slot differ on `minimum_cardinality` or `maximum_cardinality`, the converter
SHALL write each usage's own bound into its class's `slot_usage`: the lower bound for the minimum,
and the upper bound for the maximum when it is finite. A usage whose upper bound is unbounded while
the upper bound of an `is_a` ancestor's usage of the same slot, as its multiplicity gives it (a
single-valued `0..1` counts as 1), is finite SHALL be the problem `cardinality_unbounded`, through
any number of ancestors, those without attributes included.

#### Scenario: an unbounded role under a single-valued ancestor
- **GIVEN** `A` with `p 0..1`, `B` generalising `A` with `p 0..*`, and an unrelated `D` with `p 0..3`
- **WHEN** the model is converted
- **THEN** the run fails with the problem `cardinality_unbounded` on `B.p`

#### Scenario: an inherited 2..* role redrawn as 1
- **GIVEN** an abstract class `A` with a role `p 2..*` to `V`, and `B` generalising `A` that redraws `p 1` to `W`, a subclass of `V`
- **WHEN** the model is converted
- **THEN** `B.slot_usage.p` has `minimum_cardinality: 1`, and `SchemaView.induced_slot("p", "B").minimum_cardinality` is 1

#### Scenario: an inherited 0..5 role redrawn as 0..1
- **GIVEN** `A` with `p 0..5`, and `B` generalising `A` with `p 0..1`
- **WHEN** the model is converted
- **THEN** the induced `maximum_cardinality` of `p` on `B` is 1

#### Scenario: an unbounded role under a bounded ancestor
- **GIVEN** `A` with `p 0..5`, and `B` generalising `A` with `p 0..*`
- **WHEN** the model is converted
- **THEN** the run fails with the problem `cardinality_unbounded` on `B.p`

#### Scenario: an unrelated class may be unbounded
- **GIVEN** `A` with `p 0..5`, and a class `C` that does not generalise `A`, with `p 0..*`
- **WHEN** the model is converted
- **THEN** there is no problem, and `C` writes no maximum

### Requirement: Aggregates are drawn as compositions

An EA Aggregation connector whose diamond end is marked composite SHALL be read as a composition
from the class at the diamond end (the whole) to the class at the other end (the part), whatever
the direction it was drawn in. Each composition SHALL have exactly one association between the
same two classes that gives a slot on the whole ranging over the part; that slot SHALL be owned and
inlined (`inlined_as_list` when multivalued); when several associations qualify, the composition
SHALL name the one it marks by its role. Compositions SHALL nest to any depth, and a composition
to a part SHALL make each of the part's descendants a part. Compositions SHALL form a tree of
instances: a part class MAY have several whole classes and a composition MAY recurse, each
instance sitting in one whole. The run SHALL fail, naming the classes, on: a composition with no
such association, or with several and no role naming one; a shared (weak) aggregation; a
composition with both or neither end marked, or whose subtype disagrees with its marked end; a
part class no root reaches, a cycle no root enters among them; a composition whose end is outside
the converted classes, a toolkit class, an enumeration or the tenant root; an association with a
composite end (naming the two-connector form).

#### Scenario: a part is owned and inlined
- **GIVEN** `lib:Book` with an association `lib:hasChapter 1..*` to `lib:Chapter` and a
  composition from `Book` to `Chapter`
- **WHEN** the model is converted
- **THEN** `has_chapter` is `owned` and `inlined_as_list`, and `Chapter` takes the default mixins

#### Scenario: the composition drawn either way
- **GIVEN** the composition `Book ◆ Chapter` drawn from `Book` to `Chapter`, and in a second model
  from `Chapter` to `Book`, the diamond at `Book` in both
- **WHEN** both are converted
- **THEN** the schemas are identical

#### Scenario: parts three deep
- **GIVEN** compositions `Shelf ◆ Book`, `Book ◆ Chapter`, `Chapter ◆ Page`, each beside its
  association
- **WHEN** the model is converted
- **THEN** `Shelf` is the only root of the four, and the three slots are owned

#### Scenario: recursive and shared part classes
- **GIVEN** `Book ◆ Section` and `Section ◆ Section` (subsections), and `Note` the part of both
  `Book` and `Chapter`, each composition beside its association
- **WHEN** the model is converted
- **THEN** the run writes, `Book` is the only root of these, and the slots are owned

#### Scenario: two roles to one part class
- **GIVEN** `Book` with associations `lib:frontMatter` and `lib:body` to `Section`, two
  compositions each naming one of the roles, and an association `lib:firstSection` to `Section`
- **WHEN** the model is converted
- **THEN** `front_matter` and `body` are owned and `first_section` is a reference

#### Scenario: refused compositions
- **GIVEN** <model>
- **WHEN** the model is converted
- **THEN** the run fails naming <named>, and nothing is written

  | model | named |
  |---|---|
  | a composition `Book ◆ Chapter` with no association | `Book`, `Chapter`, the missing association |
  | two associations `Book → Chapter` beside one composition that names no role | both roles |
  | compositions `Chapter ◆ Page` and `Page ◆ Chapter`, no root composing either | the cycle |
  | `Chapter ◆ Page` where `Chapter` is no one's part and abstract with no root below | `Page` |
  | a composition to a class outside the converted package | the composition and the subtree |
  | a shared aggregation `Book ◇ Chapter` | the connector, and the composition to draw |
  | an association with a composite end at `Book` | the slot, and the two-connector form |

### Requirement: Roots are derived from the compositions

A class SHALL be an aggregate root when it is converted, concrete, not an enumeration, not
«tenant root», in a module of kind `domain`, and no composition's part. A class of a not-generated
stereotype or a drawn toolkit class SHALL never be a root; the abstract-root rule SHALL still
apply. The report SHALL list each root with its parts in one `root` line. When a model draws «root»
on any class, each class drawn «root» that is not derived, and each derived root not drawn
«root», SHALL fail the run naming it; when the two sets are equal, the run SHALL convert to the
schemas the derived roots give and add one `deprecated-root` line. The comparison SHALL cover the
concrete classes of domain modules: «root» on an abstract class SHALL fail the run, and «root» in
another kind of module SHALL keep its meaning. Schemas SHALL be byte-identical to a conversion
before this change when each boundary-owned association was the only association between its two
classes and is drawn as a composition.

#### Scenario: what is not a root
- **GIVEN** <class>
- **WHEN** the model is converted
- **THEN** it is not an aggregate root

  | class |
  |---|
  | `lib:Chapter`, a composition's part |
  | an abstract `lib:Publication` with no all-root descendants |
  | `lib:Authority` stereotyped «loaded graph» (not generated) |
  | a drawn `rp:RoleDefinition` |
  | `lib:Library` stereotyped «tenant root» |
  | a class of a package tagged `module_kind=access` with no «root» drawn and no toolkit root parent |

#### Scenario: the roots are reported
- **GIVEN** roots `Shelf` (parts `Book`, `Chapter`) and `Reader` (no part)
- **WHEN** the model is converted
- **THEN** the report has `root` lines for `Reader` with no parts and `Shelf` with `Book, Chapter`

#### Scenario: a «root» that disagrees
- **GIVEN** a model that draws «root» on `Shelf` but not on `Reader`, which is no one's part
- **WHEN** it is converted
- **THEN** the run fails naming `Reader` as a derived root not drawn «root»; drawing «root» on
  `Chapter`, a part, fails naming `Chapter` and its whole

#### Scenario: «root» and compositions that agree
- **GIVEN** the library model drawn with «root» and boundaries, converted before this change, and
  the same model with a composition beside each owned association
- **WHEN** the second is converted
- **THEN** its schema files are byte-identical to the first's, the report adds `root` lines and
  one `deprecated-root` line, and `rp-uml2linkml --check` does not fail on that line

### Requirement: A part stored in its own graph

A composition stereotyped «own graph» SHALL make its part stored apart from its whole and deleted
with it. Its part SHALL be a class of a not-generated stereotype: the whole's slot then ranges over
`uri`, is not owned, and carries the annotation `rp_loaded_graph: true`; a class below that part by
a plain composition SHALL not be converted and SHALL be reported. An «own graph» composition to a
generated class SHALL convert the part to a dependent root (the change `dependent-aggregates`,
which superseded this change's refusal on 2026-11-28). A plain composition to
a not-generated class, and any other stereotype on a composition, SHALL fail the run.

#### Scenario: loaded reports of a shelf count
- **GIVEN** `lib:ShelfCount` with «own graph» compositions to `lib:CountReport` and
  `lib:ShapeReport`, both «loaded graph», and a plain composition `ShapeReport ◆ lib:ShapeResult`,
  each beside its association
- **WHEN** the model is converted
- **THEN** `count_report` and `shape_report` range over `uri` with `rp_loaded_graph: true` and no
  `owned`, `ShapeResult` is not generated and is reported, and `ShelfCount` is a root

#### Scenario: a generated part in its own graph
- **GIVEN** `lib:Inventory` with an «own graph» composition to the generated `lib:ShelfCount`
- **WHEN** the model is converted
- **THEN** `ShelfCount` is a root annotated `rp_dependent_on`, its pointer to `Inventory` required
  and single-valued (the change `dependent-aggregates` replaced the refusal this change first had)

### Requirement: Pointers target roots

An association slot that is not owned and ranges over a composition part (or an abstract class all
of whose concrete descendants are parts) SHALL fail the run, naming the slot, the part and its
roots, unless the holder belongs to an aggregate the part belongs to. A slot over any other class
(a root, the tenant root, a class of a non-domain module) SHALL convert as before. A domain role
IRI owned on one class and used as a pointer elsewhere SHALL fail the run; a role kept as a toolkit
slot is exempt.

#### Scenario: a pointer into another aggregate's part
- **GIVEN** `Shelf ◆ Book` and an association `lib:Reader → lib:Book` named `lib:borrows`
- **WHEN** the model is converted
- **THEN** the run fails naming `Reader.borrows`, `Book` and `Shelf`; pointing at `Shelf` converts

#### Scenario: a pointer to a class that is no part
- **GIVEN** an association from `lib:Book` to a class of a package tagged `module_kind=access`
- **WHEN** the model is converted
- **THEN** the slot converts as before, a reference by IRI

#### Scenario: an abstract «root»
- **GIVEN** a model that draws «root» on the abstract `lib:Publication`
- **WHEN** it is converted
- **THEN** the run fails naming `Publication`; the abstract-root rule derives it

### Requirement: The conventions check

Every convention of the UML conventions page SHALL be a finding: a convention whose breach changes
the generated LinkML a problem, any other a convention line of the report. `rp-uml2linkml --check`
SHALL read and convert the model as a run does, write nothing (no schema, no side file, no report),
print the problems or, when there is none, the convention lines, and exit 1 when there is any, 0
otherwise, 2 on a usage error (a problem stops the check as it stops a run). A normal run SHALL write on convention lines. Only diagram names and the elements and
connectors a diagram shows SHALL be read: an aggregates diagram (`<package> · aggregates`) SHALL
show classes and compositions only (notes, text, boundaries, note links and generalisations
allowed), and no other class diagram of a converted package SHALL show a composition. When the
converter's reader finds problems, the check SHALL report those alone. A reference collection drawn
as the conventions page prescribes SHALL pass the check.

#### Scenario: a check writes nothing
- **GIVEN** a model with one problem and an output folder holding an earlier conversion
- **WHEN** `rp-uml2linkml --check` runs on it
- **THEN** it prints the problem, exits 1, and the folder is unchanged

#### Scenario: a clean model
- **GIVEN** a model with no problem and no convention line
- **WHEN** `rp-uml2linkml --check` runs without `--out`
- **THEN** it exits 0 and prints nothing

#### Scenario: each convention fails the check
- **GIVEN** a clean model seeded with <breach>
- **WHEN** `rp-uml2linkml --check` runs
- **THEN** it exits 1 with a <finding> naming the element

  | breach | finding |
  |---|---|
  | a class without a prefix | `unprefixed-name` line |
  | an association with no multiplicity | `unspecified-multiplicity` line |
  | a class without a note | `no-note` line |
  | a concrete class drawn «root» that is a part | `root_class` problem |
  | an enumeration no dependency uses | `unused-enumeration` line |
  | two packages giving one module name | `package_module` problem |
  | a role owned on `Book` and a pointer on `Reader` | `boundary_owned` problem |
  | a pointer into another aggregate's part | `boundary_owned` problem |
  | a generalisation to a drawn toolkit class | `drawn-toolkit-parent` line |
  | a required pointer from the tenant root to a root | `tenant-required-pointer` line |
  | a boundary named for a class that is no root | `boundary-disagrees` line |

#### Scenario: the reference collection pattern passes the check
- **GIVEN** an abstract `lib:Collection` tagged `rp_mixins=ReferenceCollection` whose `dct:hasPart`
  role stays the toolkit's `has_part`, and `lib:Shelf` narrowing it to `lib:Book`, otherwise clean
- **WHEN** `rp-uml2linkml --check` runs
- **THEN** it exits 0; the report's `toolkit-slot-kept` line is informational

#### Scenario: an aggregates diagram holding an association
- **GIVEN** a diagram `catalogue · aggregates` that shows the association `lib:hasChapter`
- **WHEN** the model is converted
- **THEN** the run writes, the report has an `aggregates-diagram` line naming the diagram and the
  association, and `--check` exits 1

#### Scenario: a composition on an association diagram
- **GIVEN** a diagram `catalogue` that shows the composition `Book ◆ Chapter`
- **WHEN** `--check` runs
- **THEN** it exits 1 with a `composition-diagram` line

### Requirement: An «own graph» composition to a generated part converts to a dependent root

`rp-uml2linkml` SHALL convert the part of an «own graph» composition that is a generated class into
an aggregate root annotated `rp_dependent_on: <slot>`, where the slot is the association's role on
the whole's end, required, single-valued and ranging over the whole. An association with no role on
the whole's end, or whose multiplicity there is not `1`, SHALL be a problem naming it. A role on the
part's end SHALL not be converted and SHALL get a report line. `rp-generate` SHALL accept the output.

#### Scenario: a generated «own graph» part
- **GIVEN** `Audit` ◆«own graph» `AuditResult`, the association's role `of_audit` on `Audit`'s end
  with multiplicity `1`
- **WHEN** `rp-uml2linkml` runs
- **THEN** `AuditResult` is a root annotated `rp_dependent_on: of_audit`, `of_audit` is required and
  ranges over `Audit`, `Audit` has no slot listing results, and `rp-generate` accepts the output

#### Scenario: no pointer role
- **GIVEN** the same composition with no role on `Audit`'s end
- **WHEN** `rp-uml2linkml` runs
- **THEN** it fails with a problem naming the association
