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
class fixes the collection's `member_class` to that class.

#### Scenario: a reference collection's member class
- **GIVEN** `«root» lib:Shelf` tagged `rp_mixins=ReferenceCollection` (or generalising a class that
  is) with a `dct:hasPart` role to `«root» lib:Book`
- **WHEN** it is converted
- **THEN** `Shelf` has `slot_usage: {member_class: {equals_string: Book}}`, a `Shelf` of another
  member class is refused by its model and its shape, and the report has no `toolkit-slot-kept`
  line for the role; a role to `Shelf` itself (nesting) stays the toolkit's `has_part`, reported as
  before, and roles to two different classes fail the run naming `Shelf`

#### Scenario: a root that is an activity
- **GIVEN** `«root» lib:Loan` tagged `rp_mixins=Activity` with `prov:startedAtTime [1..1]` and `rp_path=loans`
- **WHEN** it is converted
- **THEN** `Loan` is `is_a: Activity`, mixes in `AggregateRoot`, `Described` and `Tracked`, has
  `annotations: {rp_path: loans}`, defines no new slot and narrows no toolkit-filled slot (the
  `[1..1]` on `started_at_time` is dropped), and the report names `started_at_time`

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
