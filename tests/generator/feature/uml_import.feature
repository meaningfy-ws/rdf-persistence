Feature: A UML class model becomes LinkML that the toolkit accepts
  As a team that models its domain in Enterprise Architect
  I want one command to turn the model into the LinkML modules of my application
  So that I draw the domain once and the generator does the rest

  # spec: rp-uml-import / a package with a root and a part
  Scenario: A package with a root and a part
    Given a library package where the book is a root that owns its chapters in one boundary
    When the model is converted
    Then the conversion succeeds
    And the book is an aggregate root
    And the book's path is "books"
    And the book specialises the class "Resource"
    And the book's chapters slot is owned
    And the book's chapters slot is multivalued
    And its minimum cardinality is "2"
    And its maximum cardinality is "5"
    And the slot "title" has the IRI "dcterms:title"
    And the slot "chapters" has the IRI "lib:chapters"
    And the book's slot "genre" ranges over the enumeration "Genre"
    And the generator's lint and boundary checks accept the output

  # spec: rp-uml-import / packages that refer to each other
  Scenario: Packages that refer to each other
    Given two packages whose classes refer to each other
    When the model is converted
    Then the conversion succeeds
    And both packages are written as the one module "app_books"
    And the module "app_books" holds the classes "Book" and "Shelf"
    And the report has a "merged-cycle" line that names the packages "books" and "shelves"

  # spec: rp-uml-import / an element without a note
  Scenario: An element without a note
    Given a book class with no note
    When the model is converted
    Then the conversion succeeds
    And the book has no description
    And the report has a "no-note" line naming "Book"

  # spec: rp-uml-import / multiplicity
  Scenario Outline: Multiplicity
    Given a book with an association to chapters whose multiplicity is "<card>"
    When the model is converted
    Then the conversion succeeds
    And the chapters slot is required "<required>"
    And the chapters slot is multivalued "<many>"
    And its minimum cardinality is "<minimum>"
    And its maximum cardinality is "<maximum>"
    And the report has "<lines>" "unspecified-multiplicity" lines

    Examples:
      | card | required | many  | minimum | maximum | lines |
      | 0..1 | no       | no    | none    | none    | no    |
      | 1..1 | yes      | no    | none    | none    | no    |
      | 1..* | yes      | yes   | none    | none    | no    |
      | 2..5 | yes      | yes   | 2       | 5       | no    |
      | none | no       | yes   | none    | none    | one   |

  # spec: rp-uml-import / an enumeration with no literals
  Scenario: An enumeration with no literals
    Given a book that depends on an enumeration with no literals
    When the model is converted
    Then the conversion succeeds
    And the slot to the enumeration ranges over "uri"
    And the report has an "external-list" line naming "Language"

  # spec: rp-uml-import / a language string
  Scenario: A language string
    Given a book with an attribute typed "rdf:langString"
    When the model is converted
    Then the conversion fails
    And the error names "Book.summary"
    And the error names "rdf:langString"
    And nothing is written

  # spec: rp-uml-import / a connector's direction
  Scenario Outline: A connector's direction
    Given a book associated to chapters in the direction "<direction>" with a source role "<source role>"
    When the model is converted
    Then the conversion fails
    And the error names "Book"
    And the error names "<message>"

    Examples:
      | direction             | source role | message                         |
      | Destination -> Source | none        | direction Destination -> Source |
      | Source -> Destination | owner       | needs Bi-Directional            |

  # spec: rp-uml-import / an abstract class drawn with a stereotype
  Scenario: An abstract class drawn with a stereotype
    Given a class "Work" stereotyped "Abstract"
    When the model is converted
    Then the conversion succeeds
    And the class "Work" is abstract

  # spec: rp-uml-import / an element no rule maps
  Scenario: An element no rule maps
    Given a book and a chapter joined by an association class
    When the model is converted
    Then the conversion fails
    And the error names "association class"
    And the error names "no rule converts it"
    And nothing is written

  # spec: rp-uml-import / stable output
  Scenario: Stable output
    Given a library package where the book is a root that owns its chapters in one boundary
    When the model is converted
    And the model is converted again
    Then the second output is byte-identical to the first

  # spec: rp-uml-import / a root that is an activity
  Scenario: A root that is an activity
    Given a loan that is a root tagged "rp_mixins=Activity" and "rp_path=loans" with a started time of 1..1
    When the model is converted
    Then the conversion succeeds
    And the loan is an activity
    And the loan is an aggregate root with the mixins "Described" and "Tracked"
    And the loan's path is "loans"
    And the loan defines no slot of its own
    And the loan narrows no slot
    And the loan lists no slot
    And the report names "started_at_time"

  # spec: rp-uml-import / a tagged value becomes an annotation
  Scenario: A tagged value becomes an annotation
    Given a book root tagged "rp_writes=service"
    When the model is converted
    Then the conversion succeeds
    And the class "Book" carries the annotation "rp_writes" with the value "service"

  # spec: rp-uml-import / a tagged value becomes an annotation (a value that is not allowed)
  Scenario: A tagged value outside the allowed values
    Given a book root tagged "rp_writes=sometimes"
    When the model is converted
    Then the conversion fails
    And the error names "Book"
    And the error names "sometimes"

  # spec: rp-uml-import / a business identifier
  Scenario: A business identifier
    Given a book root with the attribute "dct:identifier" of type "xsd:string" and multiplicity 1..1
    When the model is converted
    Then the conversion succeeds
    And the slot "identifier" has the IRI "dcterms:identifier"
    And the slot "identifier" is a string
    And the slot "identifier" is required
    And the book has the slot "identifier"
    And the library defines no slot "id"

  # spec: rp-uml-import / an excluded package
  Scenario: An excluded package
    Given a book associated to a loan in the package "circulation"
    When the model is converted leaving out the package "circulation"
    Then the conversion succeeds
    And the book has no slot "loan"
    And the library defines no slot "loan"
    And the report has an "excluded-link" line naming "Book.loan"

  # spec: rp-uml-import / three roles
  Scenario: Three roles
    Given three role definition objects with valid run-state values
    When the model is converted
    Then the conversion succeeds
    And the roles file holds the three roles "librarian", "member" and "reader"
    And the library's role loader reads the roles file
    And the report has a "role" line naming "reader"

  # spec: rp-uml-import / an unknown level
  Scenario: An unknown level
    Given a role definition object "visitor" with the level "planet"
    When the model is converted
    Then the conversion fails
    And the error names "visitor"
    And the error names "planet"
    And nothing is written

  # spec: rp-uml-import / a drawn workflow
  Scenario: A drawn workflow
    Given a Statechart diagram "lib:loan" with an Initial node, four states and five tagged transitions, and a class tagged "workflow=loan"
    When the model is converted
    Then the conversion succeeds
    And the library's workflow loader reads the file "workflows/loan.workflow.yaml"
    And the workflow has the states "approved", "refused", "requested" and "returned"
    And the workflow has the initial state "requested"
    And the workflow has the five transitions the diagram draws
    And the workflow's IRI is "https://example.org/ns/library#loan"
    And the report has a "workflow" line naming "lib:loan"

  # spec: rp-uml-import / a collection of collections
  Scenario: A collection of collections
    Given a shelf root tagged "rp_mixins=ReferenceCollection" whose only part role points at the shelf
    When the model is converted
    Then the conversion succeeds
    And the shelf's member class is fixed to "Shelf"
    And the report has "no" "toolkit-slot-kept" lines

  # spec: rp-uml-import / an undefined role
  Scenario: An undefined role
    Given a Statechart diagram "lib:loan" whose transition from "requested" to "approved" is tagged "roles=archivist", and no role definition "archivist"
    When the model is converted
    Then the conversion fails
    And the error names "requested -> approved"
    And the error names "archivist"
    And nothing is written

  # spec: rp-uml-import / a tenant root
  Scenario: A tenant root
    Given a class "Library" stereotyped "tenant root"
    When the model is converted
    Then the conversion succeeds
    And the class "Library" carries the annotation "graph" with the value "meta"
    And the class "Library" does not mix in "AggregateRoot"
    And the class "Library" has no annotation "rp_path"

  # spec: rp-uml-import / an abstract root
  Scenario: An abstract root
    Given an abstract class whose concrete subclasses are all roots, and a slot ranging over it
    When the model is converted
    Then the conversion succeeds
    And the class "Item" mixes in "AggregateRoot"
    And the class "Item" has no annotation "rp_path"
    And the class "Book" mixes in "AggregateRoot"
    And the class "Magazine" mixes in "AggregateRoot"
