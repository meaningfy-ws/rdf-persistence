Feature: A UML class model becomes LinkML that the toolkit accepts
  As a team that models its domain in Enterprise Architect
  I want one command to turn the model into the LinkML modules of my application
  So that I draw the domain once and the generator does the rest

  # spec: rp-uml-import / a package with a root and a part
  Scenario: A package with a root and a part
    Given a library package where the book owns its chapters through a composition
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
    And the packages are written as the modules "app_books" and "app_shelves" that import each other
    And the report has no line about a cycle

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
    Given a library package where the book owns its chapters through a composition
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

  # spec: rp-uml-import / the composition drawn either way (composition.feature)
  Scenario: A book owns its chapters through a composition
    Given a library package where the book has an association "hasChapter" to its chapters
    And a composition from the book to the chapter beside it
    When the package is converted
    Then the slot "has_chapter" is owned and inlined as a list
    And the book is an aggregate root and the chapter is its part
    And the generator's lint and boundary checks accept the output

  # spec: rp-uml-import / the composition drawn either way
  Scenario: The direction a composition was drawn in does not matter
    Given the composition from the book to the chapter is drawn from the chapter to the book
    And its diamond is at the book
    When the package is converted
    Then the output is the same as when it is drawn from the book to the chapter

  # spec: rp-uml-import / parts three deep
  Scenario: Parts nest three deep
    Given compositions from the shelf to the book, from the book to the chapter and from the chapter to the page
    When the package is converted
    Then the shelf is the only root of the four
    And the slots "holds", "has_chapter" and "has_page" are owned

  # spec: rp-uml-import / a boundary moved in a layout pass
  Scenario Outline: A layout change never changes what is stored together
    Given a converted library package with a boundary around the book and its chapters
    When the boundary is <moved> and the package is converted again
    Then the schemas are byte-identical to the first conversion

    Examples:
      | moved                            |
      | shrunk so the chapter is outside |
      | slid off every class             |
      | deleted                          |

  # spec: rp-uml-import / recursive and shared part classes
  Scenario: Sections hold subsections, and a note sits under two wholes
    Given compositions from the book to the section and from the section to the section
    And the note is a part of the book and of the chapter
    When the package is converted
    Then the conversion writes
    And the book is the only root among them

  # spec: rp-uml-import / two roles to one part class
  Scenario: Two owned roles and a reference to one part class
    Given the book has associations "frontMatter" and "body" to the section, each with a composition naming its role
    And an association "firstSection" from the book to the section with no composition
    When the package is converted
    Then the slots "front_matter" and "body" are owned
    And the slot "first_section" is a reference

  # spec: rp-uml-import / refused compositions
  Scenario Outline: A composition the converter cannot read fails the run
    Given a library package with <drawing>
    When the package is converted
    Then the run fails naming <named>
    And nothing is written

    Examples:
      | drawing                                                                      | named                                             |
      | a composition from the book to the chapter and no association                | the book, the chapter and the missing association |
      | two associations beside one composition that names no role                   | both roles                                        |
      | compositions from the chapter to the page and back, no root composing either | the cycle                                         |
      | a page whose whole no root reaches                                           | the page                                          |
      | a composition to a class outside the converted package                       | the composition and the subtree                   |
      | a shared aggregation from the book to the chapter                            | the connector and the composition to draw         |
      | an association whose end at the book is composite                            | the slot and the two-connector form               |

  # spec: rp-uml-import / what is not a root (derived_roots.feature)
  Scenario Outline: A class that is not a root
    Given a library package with <class>
    When the package is converted
    Then that class is not an aggregate root

    Examples:
      | class                                                  |
      | a chapter that is the part of a book                   |
      | an abstract publication with no root below it          |
      | an authority stereotyped "loaded graph"                |
      | a drawn toolkit role definition                        |
      | the library stereotyped "tenant root"                  |
      | a plain class in a package tagged "module_kind=access" |

  # spec: rp-uml-import / the roots are reported
  Scenario: The report lists every root with its parts
    Given a shelf that holds books with chapters, and a reader that is no one's part
    When the package is converted
    Then the report has a root line for the reader with no parts
    And a root line for the shelf with the parts "Book, Chapter"

  # spec: rp-uml-import / a «root» that disagrees
  Scenario Outline: A drawn «root» that disagrees with the compositions fails
    Given a library package that draws «root» on the shelf
    And <disagreement>
    When the package is converted
    Then the run fails naming <named>

    Examples:
      | disagreement                                     | named                                 |
      | the reader is no one's part and not drawn «root» | the reader as a root not drawn «root» |
      | the chapter, a part of the book, is drawn «root» | the chapter and the book              |
      | the abstract publication is drawn «root»         | the publication                       |

  # spec: rp-uml-import / «root» and compositions that agree
  Scenario: A model drawn the old way and with compositions converts the same
    Given the library model drawn with «root» and a boundary, converted before compositions existed
    And each association its boundary owned is the only one between its two classes
    And the same model with a composition beside each owned association
    When it is converted
    Then the schema files are byte-identical to the earlier conversion
    And the report adds the root lines and one deprecated-root line

  # spec: rp-uml-import / loaded reports of a shelf count (own_graph_and_pointers.feature)
  Scenario: A shelf count keeps its loaded reports in their own graphs
    Given a shelf count with "own graph" compositions to a count report and a shape report
    And both reports are stereotyped "loaded graph"
    And the shape report holds its shape results by a plain composition
    When the package is converted
    Then the slots "count_report" and "shape_report" range over URIs and are marked as loaded graphs
    And neither slot is owned
    And the shape result is not generated and the report names it
    And the shelf count is an aggregate root

  # spec: rp-uml-import / a generated part in its own graph
  Scenario: A generated class in its own graph waits for dependent aggregates
    Given an inventory with an "own graph" composition to the generated shelf count
    When the package is converted
    Then the run fails naming the inventory, the shelf count and "dependent-aggregates"
    And nothing is written

  # spec: rp-uml-import / refused compositions (DEC-7)
  Scenario: A loaded graph cannot be an inline part
    Given a shelf count with a plain composition to a count report stereotyped "loaded graph"
    When the package is converted
    Then the run fails naming the composition and "own graph"

  # spec: rp-uml-import / a pointer into another aggregate's part
  Scenario Outline: A pointer must target a root
    Given a shelf that holds books
    And a reader whose association "borrows" points at <target>
    When the package is converted
    Then <outcome>

    Examples:
      | target          | outcome                                                        |
      | the book        | the run fails naming the reader's slot, the book and the shelf |
      | the shelf       | the package converts                                           |
      | an access class | the package converts, the slot a reference as before           |

  # spec: rp-uml-import / refused compositions (DEC-3)
  Scenario: The old composite association is refused
    Given a library package where the book owns its chapters through an association with a composite end
    When the package is converted
    Then the run fails naming the slot
    And the message says to draw a composition beside a plain association

  # spec: rp-uml-import / a role object that realises its class (#435; conventions_check.feature)
  Scenario Outline: A role object and its Realisation
    Given a role object "librarian" <classifier> and a Realisation to <target>
    When the model is converted
    Then <outcome>

    Examples:
      | classifier                   | target         | outcome                                                   |
      | classified by RoleDefinition | RoleDefinition | the roles file is the one written without the Realisation |
      | with no classifier           | RoleDefinition | it is read as a role definition                           |
      | classified by RoleDefinition | the book       | the run fails naming the object, RoleDefinition and Book  |
