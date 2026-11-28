## MODIFIED Requirements

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

## ADDED Requirements

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
generated class SHALL fail the run naming the change `dependent-aggregates`. A plain composition to
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
- **THEN** the run fails naming `Inventory`, `ShelfCount` and `dependent-aggregates`, and nothing
  is written

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
print the problems and the convention lines, and exit 1 when there is any, 0 otherwise, 2 on a usage
error. A normal run SHALL write on convention lines. Only diagram names and the elements and
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
