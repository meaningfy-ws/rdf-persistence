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
